# pylint: disable=protected-access
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import stdnum

from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import index_exists
from .mixins import ChequeIssuerMixin


class AccountPaymentCheque(ChequeIssuerMixin, models.Model):
    _name = 'account.cheque'
    _description = 'Account payment cheque'
    _check_company_auto = True
    _inherit = ['mail.thread', 'mail.activity.mixin']

    payment_id = fields.Many2one(
        'account.payment',
        required=True,
        ondelete='cascade',
    )
    operation_ids = fields.Many2many(
        comodel_name='account.payment',
        relation='cheque_account_payment_rel',
        column1="check_id",
        column2="payment_id",
        readonly=True,
        check_company=True,
    )
    current_journal_id = fields.Many2one(
        comodel_name='account.journal',
        compute='_compute_current_journal', store=True,
    )
    name = fields.Char(string='Number')
    issuer_name = fields.Char(
        string='Issuer Name',
        compute='_compute_issuer_name', store=True, readonly=False,
    )
    bank_id = fields.Many2one(
        comodel_name='res.bank',
        compute='_compute_bank_id', store=True, readonly=False,
        required=True,
    )
    issuer_vat = fields.Char(
        string='Issuer VAT',
        compute='_compute_issuer_vat', store=True, readonly=False,
    )
    payment_date = fields.Date(readonly=False, required=True)
    amount = fields.Monetary()
    outstanding_line_id = fields.Many2one('account.move.line', readonly=True, check_company=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('register', 'Registered'),
            ('deposit', 'Deposited'),
            ('cashed', 'Cashed'),
            ('bounce', 'Bounced'),
            ('voided', 'Voided'),
        ],
        string='Status',
        default='draft',
    )
    # fields from payment
    payment_method_code = fields.Char(related='payment_id.payment_method_code')
    partner_id = fields.Many2one(related='payment_id.partner_id')
    original_journal_id = fields.Many2one(related='payment_id.journal_id')
    company_id = fields.Many2one(related='payment_id.company_id', store=True)
    currency_id = fields.Many2one(related='payment_id.currency_id')
    payment_method_line_id = fields.Many2one(
        related='payment_id.payment_method_line_id',
        store=True,
    )
    payment_type = fields.Selection(
        related='payment_id.payment_type',
        string='Payment Type',
        store=True,
    )
    cashed_date = fields.Date(
        string='Cashed Date',
        readonly=True,
        help='Date when the cheque was cashed at the bank'
    )
    deposit_journal_id = fields.Many2one(
        'account.journal',
        string='Deposit Journal',
        readonly=True,
        check_company=True,
        help='Bank journal where the cheque was deposited'
    )
    deposit_date = fields.Date(
        string='Deposit Date',
        readonly=True,
        help='Date when the cheque was deposited to the bank'
    )
    collection_line_id = fields.Many2one(
        'account.move.line',
        string='Collection Line',
        readonly=True,
        check_company=True,
        help='The debit line in collection account from deposit move'
    )

    def _auto_init(self):
        super()._auto_init()
        if not index_exists(self.env.cr, 'cheque_unique'):
            # outstanding_line_id is used to know that is an own cheque and also that is posted
            self.env.cr.execute("""
                CREATE UNIQUE INDEX cheque_unique
                    ON account_cheque(name, payment_method_line_id)
                WHERE outstanding_line_id IS NOT NULL
            """)


    def _get_move_amounts(self):
        """Return (company_amount, payment_amount, currency_id) for the current cheque.

        Source priority: collection_line_id (post-deposit) → outstanding_line_id (pre-deposit)
        → cheque.amount (no line yet, e.g. legacy records).
        """
        line = self.collection_line_id or self.outstanding_line_id
        if line:
            company_amount = line.debit or line.credit
            payment_amount = abs(line.amount_currency) if line.amount_currency else company_amount
            currency_id = line.currency_id.id or self.currency_id.id
        else:
            company_amount = self.amount
            payment_amount = self.amount
            currency_id = self.currency_id.id
        return company_amount, payment_amount, currency_id

    def _build_move_line_vals(self, account_id, name, company_amount, payment_amount, currency_id, is_debit):
        """Build a single journal entry line dict (debit or credit)."""
        sign = 1 if is_debit else -1
        return {
            'account_id': account_id,
            'partner_id': self.partner_id.id,
            'name': name,
            'debit': company_amount if is_debit else 0.0,
            'credit': 0.0 if is_debit else company_amount,
            'amount_currency': sign * payment_amount,
            'currency_id': currency_id,
            'date_maturity': self.payment_date,
        }

    def _create_transition_move(self, debit_account, credit_account, journal_id, date, label, reconcile_line=None):
        """Create, post, and optionally reconcile a two-line cheque lifecycle journal entry.

        Amounts are derived from the current cheque state via _get_move_amounts().
        If reconcile_line is provided, the move line on the same account is reconciled with it.

        :param debit_account: account.account record to debit
        :param credit_account: account.account record to credit
        :param journal_id: int, journal to post in
        :param date: Date or None (defaults to today)
        :param label: str, used as move ref and both line names
        :param reconcile_line: account.move.line to reconcile with (optional)
        :return: posted account.move
        """
        company_amount, payment_amount, line_currency_id = self._get_move_amounts()
        debit  = self._build_move_line_vals(debit_account.id,  label, company_amount, payment_amount, line_currency_id, True)
        credit = self._build_move_line_vals(credit_account.id, label, company_amount, payment_amount, line_currency_id, False)
        move = self.env['account.move'].create({
            'date': date or fields.Date.today(),
            'journal_id': journal_id,
            'ref': label,
            'line_ids': [Command.create(debit), Command.create(credit)],
        })
        move.action_post()
        if reconcile_line:
            target = move.line_ids.filtered(lambda l: l.account_id == reconcile_line.account_id)
            (target + reconcile_line).reconcile()
        return move

    def _get_issuer_method_code(self):
        return self.payment_method_line_id.code

    def _get_issuer_partner(self):
        return self.payment_id.partner_id

    def _prepare_void_move_vals(self):
        """Prepare journal entry to void/return cheque and reopen the original debt."""
        counterpart_line = self.payment_id.move_id.line_ids.filtered(
            lambda l: l.account_id == self.payment_id.destination_account_id
        )
        return {
            'ref': _('Void cheque %s') % self.name,
            'journal_id': self.payment_id.journal_id.id,
            'line_ids': [
                Command.create({
                    'name': _('Void cheque %s') % self.name,
                    'date_maturity': self.outstanding_line_id.date_maturity,
                    'amount_currency': self.outstanding_line_id.amount_currency,
                    'currency_id': self.outstanding_line_id.currency_id.id,
                    'balance': self.outstanding_line_id.balance,
                    'partner_id': self.outstanding_line_id.partner_id.id,
                    'account_id': counterpart_line.account_id.id,
                }),
                Command.create({
                    'name': _('Void cheque %s') % self.name,
                    'date_maturity': self.outstanding_line_id.date_maturity,
                    'amount_currency': -self.outstanding_line_id.amount_currency,
                    'currency_id': self.outstanding_line_id.currency_id.id,
                    'balance': -self.outstanding_line_id.balance,
                    'partner_id': self.outstanding_line_id.partner_id.id,
                    'account_id': self.outstanding_line_id.account_id.id,
                }),
            ],
        }

    def action_void(self):
        """Void cheque - cancels the check and reopens the original debt."""
        voided = self.env['account.cheque']
        for rec in self:
            if not rec.payment_id or not rec.payment_id.move_id:
                continue
            # Set outstanding_line_id if not already set
            if not rec.outstanding_line_id:
                rec.outstanding_line_id = rec.payment_id.move_id.line_ids.filtered(
                    lambda l: l.account_id == rec.payment_id.outstanding_account_id
                )[:1]
            if not rec.outstanding_line_id:
                continue

            # Find the line to reconcile with
            if rec.outstanding_line_id.reconciled:
                # For bounced cheques, find unreconciled outstanding line from bounce move
                outstanding_account = rec.payment_id.outstanding_account_id
                bounce_line = rec.env['account.move.line'].search([
                    ('account_id', '=', outstanding_account.id),
                    ('partner_id', '=', rec.partner_id.id),
                    ('reconciled', '=', False),
                    ('name', 'ilike', 'Bounce: %s' % rec.name),
                ], limit=1)
                if not bounce_line:
                    continue
                reconcile_line = bounce_line
            else:
                reconcile_line = rec.outstanding_line_id

            void_move = rec.env['account.move'].create(rec._prepare_void_move_vals())
            void_move.action_post()
            (void_move.line_ids[1] + reconcile_line).reconcile()
            voided |= rec
        # Update state for successfully voided checks only
        if voided:
            voided.write({'state': 'voided'})

    def action_bounce(self):
        """
        Bounce a deposited cheque - reverses the deposit move
        Moves from Collection back to Outstanding
        """
        self.ensure_one()

        # If cheque was deposited, reverse the deposit move
        if self.state == 'deposit' and self.deposit_journal_id:
            if self.collection_line_id:
                collection_account = self.collection_line_id.account_id
            else:
                # Fallback for old cheques
                collection_account = self.deposit_journal_id.default_account_id

            outstanding_account = self.payment_id.outstanding_account_id

            label = _('Bounce: %s') % self.name
            move = self._create_transition_move(
                debit_account=outstanding_account,
                credit_account=collection_account,
                journal_id=self.deposit_journal_id.id,
                date=fields.Date.today(),
                label=label,
                reconcile_line=self.collection_line_id,
            )

            # Update outstanding_line_id to the new debit line for later void/re-deposit
            new_outstanding_line = move.line_ids.filtered(lambda l: l.account_id == outstanding_account)
            self.write({
                'state': 'bounce',
                'collection_line_id': False,
                'outstanding_line_id': new_outstanding_line.id,
            })
            return True

        return self.write({'state': 'bounce'})

    def action_draft(self):
        self.ensure_one()
        return self.write({'state': 'draft'})

    def action_deposit(self, bank_journal_id=None, deposit_date=None):
        """
        Deposit the cheque to a bank journal - creates accounting move
        Moves from Outstanding to Cheques Under Collection account
        """
        self.ensure_one()

        # If called without parameters, return wizard action
        if bank_journal_id is None:
            return {
                'name': _('Deposit Cheque'),
                'type': 'ir.actions.act_window',
                'res_model': 'cheque.deposit.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_cheque_ids': [Command.set(self.ids)],
                    'default_company_id': self.company_id.id,
                }
            }

        bank_journal = self.env['account.journal'].browse(bank_journal_id)

        collection_account = self.original_journal_id.cheque_collection_account_id
        if not collection_account:
            raise UserError(_('Please configure "Cheques Under Collection Account" on journal "%s".') % self.original_journal_id.name)

        outstanding_account = self.outstanding_line_id.account_id if self.outstanding_line_id else self.payment_id.outstanding_account_id

        label = _('Deposit: %s') % self.name
        move = self._create_transition_move(
            debit_account=collection_account,
            credit_account=outstanding_account,
            journal_id=bank_journal.id,
            date=deposit_date,
            label=label,
            reconcile_line=self.outstanding_line_id,
        )
        collection_line = move.line_ids.filtered(lambda l: l.account_id == collection_account)

        # Update cheque
        self.write({
            'state': 'deposit',
            'deposit_journal_id': bank_journal_id,
            'deposit_date': deposit_date,
            'collection_line_id': collection_line.id,
        })

        return True

    def _get_last_operation(self):
        self.ensure_one()
        return (self.payment_id + self.operation_ids).filtered(
                lambda x: x.state not in ['draft', 'canceled']).sorted(key=lambda payment: (payment.date, payment.write_date, payment._origin.id))[-1:]

    @api.depends('payment_id.state', 'operation_ids.state')
    def _compute_current_journal(self):
        for rec in self:
            last_operation = rec._get_last_operation()
            if not last_operation:
                rec.current_journal_id = False
                continue
            if last_operation.payment_type == 'inbound':
                rec.current_journal_id = last_operation.journal_id
            else:
                rec.current_journal_id = False

    def button_open_payment(self):
        self.ensure_one()
        return self.payment_id._get_records_action()

    def button_open_check_operations(self):
        ''' Redirect the user to the invoice(s) paid by this payment.
        :return:    An action on account.move.
        '''
        self.ensure_one()
        operations = ((self.operation_ids + self.payment_id).filtered(lambda x: x.state not in ['draft', 'canceled']))
        action = {
            'name': _("Cheque Operations"),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'views': [
                (self.env.ref('cheque.view_account_third_party_check_operations_tree').id, 'list'),
                (False, 'form')
            ],
            'context': {'create': False},
            'domain': [('id', 'in', operations.ids)],
        }
        return action

    def action_show_reconciled_move(self):
        self.ensure_one()
        move = self._get_reconciled_move()
        return move._get_records_action()

    def action_show_journal_entry(self):
        self.ensure_one()
        return self.outstanding_line_id.move_id._get_records_action()

    def _get_reconciled_move(self):
        reconciled_line = self.outstanding_line_id.full_reconcile_id.reconciled_line_ids - self.outstanding_line_id
        return (reconciled_line.move_id.line_ids - reconciled_line).mapped('move_id')

    @api.constrains('amount')
    def _constrains_min_amount(self):
        min_amount_error = self.filtered(lambda x: x.amount <= 0)
        if min_amount_error:
            raise ValidationError(_('The amount of the cheque must be greater than 0'))

    @api.depends('payment_method_line_id.code', 'payment_id.partner_id')
    def _compute_issuer_name(self):
        self._compute_issuer_fields()

    @api.depends('payment_method_line_id.code', 'payment_id.partner_id')
    def _compute_bank_id(self):
        self._compute_issuer_fields()

    @api.depends('payment_method_line_id.code', 'payment_id.partner_id')
    def _compute_issuer_vat(self):
        self._compute_issuer_fields()

    @api.constrains('issuer_vat')
    def _check_issuer_vat(self):
        for rec in self.filtered(lambda x: x.issuer_vat and x.company_id.country_id):
            if not self.env['res.partner']._run_vat_test(rec.issuer_vat, rec.company_id.country_id):
                error_message = self.env['res.partner']._build_vat_error_message(
                    rec.company_id.country_id.code.lower(), rec.issuer_vat, 'Cheque Issuer VAT'
                )
                raise ValidationError(error_message)

    @api.ondelete(at_uninstall=False)
    def _unlink_if_payment_is_draft(self):
        if any(check.payment_id.state != 'draft' for check in self):
            raise UserError(_("Can't delete a cheque if payment is In Process!"))

    def action_cash(self, bank_account_id, cashed_date):
        """
        Cash the cheque - create journal entry to move from collection to bank account

        :param bank_account_id: ID of the bank account to credit/debit
        :param cashed_date: Date when the cheque was cashed
        """
        self.ensure_one()

        bank_account = self.env['account.account'].browse(bank_account_id)

        if self.collection_line_id:
            collection_account = self.collection_line_id.account_id
        else:
            # Fallback for cheques deposited before this change
            collection_account = self.payment_id.outstanding_account_id

        label = _('Cashed: %s') % self.name

        if self.payment_type == 'inbound':
            debit_account, credit_account = bank_account, collection_account
        else:
            debit_account, credit_account = collection_account, bank_account

        self._create_transition_move(
            debit_account=debit_account,
            credit_account=credit_account,
            journal_id=self.deposit_journal_id.id or self.original_journal_id.id,
            date=cashed_date,
            label=label,
            reconcile_line=self.collection_line_id,
        )

        # Update cheque with cashed date and state
        self.write({'cashed_date': cashed_date, 'state': 'cashed'})

        return True
