# pylint: disable=protected-access
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
import stdnum

from odoo import models, fields, api, Command, _

_logger = logging.getLogger(__name__)
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
            ('paid', 'Paid'),
            ('deposit', 'Deposited'),
            ('warranty', 'Warranty'),
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
    paid_partner_id = fields.Many2one(
        'res.partner',
        string='Paid To',
        readonly=True,
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

        Source: outstanding_line_id (current open line) → cheque.amount (no line yet, e.g. legacy records).
        """
        line = self.outstanding_line_id
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
        if reconcile_line and reconcile_line.reconciled:
            raise UserError(_(
                'Cannot process cheque "%s": the linked accounting line '
                '(ID: %s, account: %s) is already fully reconciled.\n'
                'Possible causes:\n'
                '- This line was reconciled via Odoo\'s bank reconciliation '
                '(cheque state should have updated automatically).\n'
                '- The outstanding_line_id was not updated correctly after a '
                'previous operation (legacy data issue).\n'
                'Please verify the accounting entries for this cheque.'
            ) % (self.name, reconcile_line.id, reconcile_line.account_id.display_name))
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
            if reconcile_line.move_id.state != 'posted':
                raise UserError(_(
                    'Cannot process cheque "%s": the linked journal entry (ID: %s, ref: "%s") '
                    'is not posted (current state: "%s"). '
                    'Please re-post that journal entry before continuing.'
                ) % (
                    self.name,
                    reconcile_line.move_id.id,
                    reconcile_line.move_id.ref or reconcile_line.move_id.name,
                    reconcile_line.move_id.state,
                ))
            (move.line_ids + reconcile_line).flush_recordset(['parent_state'])
            target = move.line_ids.filtered(lambda l: l.account_id == reconcile_line.account_id)

            # --- DIAGNOSTIC LOG ---
            all_lines = target + reconcile_line
            _logger.warning(
                "CHEQUE RECONCILE [_create_transition_move] cheque=%s\n"
                "  NEW move.id=%s  move.state=%s\n"
                "  target line ids=%s\n"
                "    target parent_states (ORM)=%s\n"
                "    target move_id.state (ORM)=%s\n"
                "  reconcile_line.id=%s\n"
                "    reconcile_line.parent_state (ORM)=%s\n"
                "    reconcile_line.move_id.state (ORM)=%s\n"
                "    reconcile_line.reconciled=%s\n"
                "  NON-POSTED lines (ORM check): %s",
                self.name, move.id, move.state,
                target.ids,
                target.mapped('parent_state'),
                target.mapped('move_id.state'),
                reconcile_line.id,
                reconcile_line.parent_state,
                reconcile_line.move_id.state,
                reconcile_line.reconciled,
                [(l.id, l.parent_state, l.move_id.state) for l in all_lines if l.parent_state != 'posted'],
            )
            # --- END DIAGNOSTIC LOG ---

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

            reconcile_line = rec.outstanding_line_id

            if reconcile_line.move_id.state != 'posted':
                raise UserError(_(
                    'Cannot void cheque "%s": the linked journal entry (ID: %s, ref: "%s") '
                    'is not posted (current state: "%s"). '
                    'Please re-post that journal entry before voiding.'
                ) % (
                    rec.name,
                    reconcile_line.move_id.id,
                    reconcile_line.move_id.ref or reconcile_line.move_id.name,
                    reconcile_line.move_id.state,
                ))
            void_move = rec.env['account.move'].create(rec._prepare_void_move_vals())
            void_move.action_post()
            all_void_lines = void_move.line_ids + reconcile_line
            all_void_lines.flush_recordset(['parent_state'])
            _logger.warning(
                "CHEQUE RECONCILE [action_void] cheque=%s\n"
                "  void_move.id=%s  void_move.state=%s\n"
                "  void_move line ids=%s  parent_states=%s  move_states=%s\n"
                "  reconcile_line.id=%s  parent_state=%s  move_id.state=%s  reconciled=%s\n"
                "  NON-POSTED lines: %s",
                rec.name, void_move.id, void_move.state,
                void_move.line_ids.ids,
                void_move.line_ids.mapped('parent_state'),
                void_move.line_ids.mapped('move_id.state'),
                reconcile_line.id,
                reconcile_line.parent_state,
                reconcile_line.move_id.state,
                reconcile_line.reconciled,
                [(l.id, l.parent_state, l.move_id.state)
                 for l in all_void_lines if l.parent_state != 'posted'],
            )
            (void_move.line_ids[1] + reconcile_line).reconcile()
            rec.outstanding_line_id = void_move.line_ids[0]
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
            if self.outstanding_line_id:
                collection_account = self.outstanding_line_id.account_id
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
                reconcile_line=self.outstanding_line_id,
            )

            # Update outstanding_line_id to the new debit line for later void/re-deposit
            new_outstanding_line = move.line_ids.filtered(lambda l: l.account_id == outstanding_account)
            self.write({
                'state': 'bounce',
                'outstanding_line_id': new_outstanding_line.id,
            })
            return True

        return self.write({'state': 'bounce'})

    def action_take_back(self):
        """Reverse the outbound use of the cheque. State: paid → register."""
        self.ensure_one()
        if self.state != 'paid':
            raise UserError(_('Only paid cheques can be taken back.'))

        # --- DIAGNOSTIC LOG ---
        _logger.warning(
            "CHEQUE TAKE BACK [%s] state=%s\n"
            "  payment_id: id=%s  code=%s  state=%s  type=%s\n"
            "  operation_ids (%d total):\n%s",
            self.name, self.state,
            self.payment_id.id,
            self.payment_id.payment_method_code,
            self.payment_id.state,
            self.payment_id.payment_type,
            len(self.operation_ids),
            '\n'.join(
                '    [%d] id=%s  code=%s  state=%s  type=%s' % (
                    i, p.id, p.payment_method_code, p.state, p.payment_type
                )
                for i, p in enumerate(self.operation_ids)
            ) or '    (none)',
        )
        # --- END DIAGNOSTIC LOG ---

        op_posted = self.operation_ids.filtered(
            lambda p: p.payment_method_code == 'cheque_existing_out'
            and p.move_id.state == 'posted'
        )[:1]
        op_cancelled = self.operation_ids.filtered(
            lambda p: p.payment_method_code == 'cheque_existing_out' and p.state == 'cancel'
        )[:1]

        if op_posted:
            debit_account = self.outstanding_line_id.account_id
            credit_account = op_posted.destination_account_id
            label = _('Take Back: %s') % self.name

            # JE_A_line: original receipt line on the outstanding account
            je_a_line = self.payment_id.move_id.line_ids.filtered(
                lambda l: l.account_id == debit_account
            )[:1]

            # Create JE_C without internal Rec1 (reconcile_line=None)
            je = self._create_transition_move(
                debit_account=debit_account,
                credit_account=credit_account,
                journal_id=op_posted.journal_id.id,
                date=fields.Date.today(),
                label=label,
                reconcile_line=None,
            )

            jec_dr = je.line_ids.filtered(lambda l: l.account_id == debit_account)
            jec_cr = je.line_ids.filtered(lambda l: l.account_id == credit_account)

            # Guard: undo auto-reconcile if action_post() closed jec_dr
            if jec_dr and jec_dr.reconciled:
                jec_dr.remove_move_reconcile()

            # Rec1: close JE_A_line ↔ JE_B_line; leaves jec_dr OPEN
            if je_a_line and self.outstanding_line_id and not self.outstanding_line_id.reconciled:
                (je_a_line + self.outstanding_line_id).reconcile()

            # Rec2: unreconcile op_dr from vendor bills if needed, then reconcile with jec_cr
            op_dr = op_posted.move_id.line_ids.filtered(
                lambda l: l.account_id == credit_account
            )[:1]
            if op_dr and jec_cr:
                if op_dr.reconciled:
                    op_dr.remove_move_reconcile()
                (jec_cr + op_dr).reconcile()

            # outstanding_line_id → jec_dr (OPEN, points to JE_C)
            new_outstanding_line = jec_dr[:1]

        elif op_cancelled:
            pass  # Accounting already reversed by cancellation
            # Restore to JE_A_line for cancelled case
            new_outstanding_line = self.payment_id.move_id.line_ids.filtered(
                lambda l: l.account_id == self.payment_id.outstanding_account_id
            )[:1]
        else:
            raise UserError(_('Cannot take back: no linked payment found for cheque %s.') % self.name)

        self.write({
            'state': 'register',
            'paid_partner_id': False,
            'outstanding_line_id': new_outstanding_line.id if new_outstanding_line else False,
        })

    def action_reset_to_register(self):
        """Reset a bounced cheque to register state. State: bounce → register."""
        self.ensure_one()
        if self.state != 'bounce':
            raise UserError(_('Only bounced cheques can be reset to register.'))
        self.write({'state': 'register'})

    def action_transfer(self):
        self.ensure_one()
        return {
            'name': _('Transfer Cheque'),
            'type': 'ir.actions.act_window',
            'res_model': 'cheque.transfer.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_cheque_id': self.id,
                'active_id': self.id,
                'active_model': 'account.cheque',
            },
        }

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
        collection_line = move.line_ids.filtered(lambda l: l.debit > 0)[:1]

        # Update cheque
        self.write({
            'state': 'deposit',
            'deposit_journal_id': bank_journal_id,
            'deposit_date': deposit_date,
            'outstanding_line_id': collection_line.id,
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
        if not move:
            raise UserError(_('No reconciled journal entry found for this cheque.'))
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

        if self.outstanding_line_id:
            collection_account = self.outstanding_line_id.account_id
        else:
            # Fallback for cheques deposited before this change
            collection_account = self.payment_id.outstanding_account_id

        label = _('Cashed: %s') % self.name

        if self.payment_type == 'inbound':
            debit_account, credit_account = bank_account, collection_account
        else:
            debit_account, credit_account = collection_account, bank_account

        move = self._create_transition_move(
            debit_account=debit_account,
            credit_account=credit_account,
            journal_id=self.deposit_journal_id.id or self.original_journal_id.id,
            date=cashed_date,
            label=label,
            reconcile_line=self.outstanding_line_id,
        )

        bank_line = move.line_ids.filtered(lambda l: l.account_id == bank_account)
        # Update cheque with cashed date and state
        self.write({'cashed_date': cashed_date, 'state': 'cashed', 'outstanding_line_id': bank_line.id})

        return True

    def _audit_outstanding_consistency(self):
        """Return a list of dicts for cheques whose outstanding_line_id is
        inconsistent with their state.

        Covers:
          - state='deposit' + outstanding_line_id missing
          - state='deposit' + outstanding_line_id.reconciled=True (stale pointer)
        """
        issues = []
        deposit_cheques = self.search([('state', '=', 'deposit')])
        for cheque in deposit_cheques:
            line = cheque.outstanding_line_id
            if not line:
                issues.append({
                    'cheque': cheque,
                    'type': 'missing_outstanding',
                    'detail': 'No outstanding_line_id while state=deposit',
                })
            elif line.reconciled:
                issues.append({
                    'cheque': cheque,
                    'type': 'stale_outstanding',
                    'detail': (
                        'outstanding_line_id=%s (account=%s) '
                        'is reconciled — stale pointer'
                    ) % (line.id, line.account_id.name),
                })
        return issues

    def _cron_audit_outstanding(self):
        """Cron entry point: audit and log outstanding_line_id anomalies."""
        issues = self._audit_outstanding_consistency()
        if not issues:
            _logger.info("Cheque cron audit: no anomalies found.")
            return
        for issue in issues:
            _logger.warning(
                "Cheque cron audit: %s (ID=%s) — %s: %s",
                issue['cheque'].name, issue['cheque'].id,
                issue['type'], issue['detail'],
            )
        _logger.warning("Cheque cron audit: %d anomalies found.", len(issues))

    def action_audit_outstanding(self):
        """Server action entry point: audit and log outstanding_line_id anomalies."""
        issues = self._audit_outstanding_consistency()
        if not issues:
            _logger.info("Cheque audit: no outstanding_line_id anomalies found.")
            raise UserError(_('No anomalies found. All deposited cheques have consistent outstanding lines.'))
        for issue in issues:
            _logger.warning(
                "Cheque audit: %s (ID=%s) — %s: %s",
                issue['cheque'].name, issue['cheque'].id,
                issue['type'], issue['detail'],
            )
        summary = '\n'.join(
            '• %s (ID %s): %s' % (i['cheque'].name, i['cheque'].id, i['detail'])
            for i in issues
        )
        raise UserError(_(
            'Found %d anomalous cheque(s):\n\n%s'
        ) % (len(issues), summary))
