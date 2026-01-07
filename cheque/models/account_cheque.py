# pylint: disable=protected-access
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
import stdnum

from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import index_exists


_logger = logging.getLogger(__name__)


class AccountPaymentCheque(models.Model):
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
    issuer_partner_id = fields.Many2one(
        'res.partner',
        string='Cheque Issuer',
        help='Partner who owns this cheque (for third-party cheques). Leave empty for normal cheques.'
    )
    bank_id = fields.Many2one(
        comodel_name='res.bank',
        compute='_compute_bank_id', store=True, readonly=False,
    )
    issuer_vat = fields.Char(
        compute='_compute_issuer_vat', store=True, readonly=False,
    )
    payment_date = fields.Date(readonly=False, required=True)
    amount = fields.Monetary()
    outstanding_line_id = fields.Many2one('account.move.line', readonly=True, check_company=True)
    issue_state = fields.Selection(
        selection=[('handed', 'Handed'), ('debited', 'Debited'), ('voided', 'Voided')],
        compute='_compute_issue_state',
        store=True
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('register', 'Registered'),
            ('deposit', 'Deposited'),
            ('done', 'Done'),
            ('transfer', 'Transfered'),
            ('bounce', 'Bounced'),
            ('return', 'Returned'),
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

    def _auto_init(self):
        super()._auto_init()
        if not index_exists(self.env.cr, 'cheque_unique'):
            # issue_state is used to know that is an own cheque and also that is posted
            self.env.cr.execute("""
                CREATE UNIQUE INDEX cheque_unique
                    ON account_cheque(name, payment_method_line_id)
                WHERE outstanding_line_id IS NOT NULL
            """)

    @api.onchange('name')
    def _onchange_name(self):
        if self.name:
            self.name = self.name.zfill(8)

    def _prepare_void_move_vals(self):
        return {
            'ref': 'Void cheque',
            'journal_id': self.outstanding_line_id.move_id.journal_id.id,
            'line_ids': [
                Command.create({
                    'name': "Void cheque %s" % self.outstanding_line_id.name,
                    'date_maturity': self.outstanding_line_id.date_maturity,
                    'amount_currency': self.outstanding_line_id.amount_currency,
                    'currency_id': self.outstanding_line_id.currency_id.id,
                    'debit': self.outstanding_line_id.debit,
                    'credit': self.outstanding_line_id.credit,
                    'partner_id': self.outstanding_line_id.partner_id.id,
                    'account_id': self.payment_id.destination_account_id.id,
                }),
                Command.create({
                    'name': "Void cheque %s" % self.outstanding_line_id.name,
                    'date_maturity': self.outstanding_line_id.date_maturity,
                    'amount_currency': -self.outstanding_line_id.amount_currency,
                    'currency_id': self.outstanding_line_id.currency_id.id,
                    'debit': -self.outstanding_line_id.debit,
                    'credit': -self.outstanding_line_id.credit,
                    'partner_id': self.outstanding_line_id.partner_id.id,
                    'account_id': self.outstanding_line_id.account_id.id,
                }),
            ],
        }

    @api.depends('outstanding_line_id.amount_residual')
    def _compute_issue_state(self):
        for rec in self:
            if not rec.outstanding_line_id:
                rec.issue_state = False
            elif rec.amount and not rec.outstanding_line_id.amount_residual:
                if any(
                    line.account_id.account_type in ['liability_payable', 'asset_receivable']
                    for line in rec.outstanding_line_id.matched_debit_ids.debit_move_id.move_id.line_ids
                ):
                    rec.issue_state = 'voided'
                else:
                    rec.issue_state = 'debited'
            else:
                rec.issue_state = 'handed'

    def action_void(self):
        for rec in self.filtered('outstanding_line_id'):
            void_move = rec.env['account.move'].create(rec._prepare_void_move_vals())
            void_move.action_post()
            (void_move.line_ids[1] + rec.outstanding_line_id).reconcile()

    def action_bounce(self):
        """
        Bounce a deposited cheque - reverses the deposit move
        """
        self.ensure_one()

        # If cheque was deposited, reverse the deposit move
        if self.state == 'deposit' and self.deposit_journal_id:
            Move = self.env['account.move']

            # Get accounts from deposit
            bank_account = self.deposit_journal_id.default_account_id
            outstanding_account = self.outstanding_line_id.account_id if self.outstanding_line_id else self.payment_id.outstanding_account_id

            # Reverse deposit: Debit Outstanding, Credit Bank
            debit_line = {
                'account_id': outstanding_account.id,
                'partner_id': self.partner_id.id,
                'name': _('Bounce: %s') % self.name,
                'debit': self.amount,
                'credit': 0.0,
                'date_maturity': self.payment_date,
            }
            credit_line = {
                'account_id': bank_account.id,
                'partner_id': self.partner_id.id,
                'name': _('Bounce: %s') % self.name,
                'debit': 0.0,
                'credit': self.amount,
                'date_maturity': self.payment_date,
            }

            move_vals = {
                'date': fields.Date.today(),
                'journal_id': self.deposit_journal_id.id,
                'ref': _('Bounce: %s') % self.name,
                'line_ids': [(0, 0, debit_line), (0, 0, credit_line)]
            }
            move = Move.create(move_vals)
            move.action_post()

        return self.write({'state': 'bounce'})

    def action_draft(self):
        self.ensure_one()
        return self.write({'state': 'draft'})

    def _prepare_return_move_vals(self):
        # Get counterpart line (receivable) from payment move
        counterpart_line = self.payment_id.move_id.line_ids.filtered(
            lambda l: l.account_id == self.payment_id.destination_account_id
        )
        return {
            'ref': 'Return cheque %s' % self.name,
            'journal_id': self.payment_id.journal_id.id,
            'line_ids': [
                Command.create({
                    'name': "Return cheque %s" % self.name,
                    'date_maturity': counterpart_line.date_maturity,
                    'amount_currency': -counterpart_line.amount_currency,
                    'currency_id': counterpart_line.currency_id.id,
                    'debit': counterpart_line.credit,
                    'credit': counterpart_line.debit,
                    'partner_id': counterpart_line.partner_id.id,
                    'account_id': counterpart_line.account_id.id,
                }),
                Command.create({
                    'name': "Return cheque %s" % self.name,
                    'date_maturity': self.outstanding_line_id.date_maturity,
                    'amount_currency': -self.outstanding_line_id.amount_currency,
                    'currency_id': self.outstanding_line_id.currency_id.id,
                    'debit': self.outstanding_line_id.credit,
                    'credit': self.outstanding_line_id.debit,
                    'partner_id': self.outstanding_line_id.partner_id.id,
                    'account_id': self.outstanding_line_id.account_id.id,
                }),
            ],
        }

    def action_return(self):
        for rec in self:
            if not rec.payment_id or not rec.payment_id.move_id:
                continue
            # Get liquidity line from payment move if outstanding_line_id not set
            if not rec.outstanding_line_id:
                rec.outstanding_line_id = rec.payment_id.move_id.line_ids.filtered(
                    lambda l: l.account_id == rec.payment_id.outstanding_account_id
                )[:1]
            if rec.outstanding_line_id:
                return_move = rec.env['account.move'].create(rec._prepare_return_move_vals())
                return_move.action_post()
                (return_move.line_ids[1] + rec.outstanding_line_id).reconcile()
        return self.write({'state': 'return'})

    def action_deposit(self, bank_journal_id=None, deposit_date=None):
        """
        Deposit the cheque to a bank journal - creates accounting move
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
                    'default_cheque_ids': [(6, 0, self.ids)],
                    'default_company_id': self.company_id.id,
                }
            }

        # Create deposit accounting move
        Move = self.env['account.move']
        bank_journal = self.env['account.journal'].browse(bank_journal_id)
        bank_account = bank_journal.default_account_id

        # Use outstanding line's account for reconciliation
        outstanding_account = self.outstanding_line_id.account_id if self.outstanding_line_id else self.payment_id.outstanding_account_id

        # Debit: Bank, Credit: Outstanding
        debit_line = {
            'account_id': bank_account.id,
            'partner_id': self.partner_id.id,
            'name': _('Deposit: %s') % self.name,
            'debit': self.amount,
            'credit': 0.0,
            'date_maturity': self.payment_date,
        }
        credit_line = {
            'account_id': outstanding_account.id,
            'partner_id': self.partner_id.id,
            'name': _('Deposit: %s') % self.name,
            'debit': 0.0,
            'credit': self.amount,
            'date_maturity': self.payment_date,
        }

        move_vals = {
            'date': deposit_date or fields.Date.today(),
            'journal_id': bank_journal.id,
            'ref': _('Deposit: %s') % self.name,
            'line_ids': [(0, 0, debit_line), (0, 0, credit_line)]
        }
        move = Move.create(move_vals)
        move.action_post()

        # Reconcile with outstanding line
        if self.outstanding_line_id:
            (move.line_ids.filtered(lambda l: l.account_id == outstanding_account) + self.outstanding_line_id).reconcile()

        # Update cheque
        self.write({
            'state': 'deposit',
            'deposit_journal_id': bank_journal_id,
            'deposit_date': deposit_date,
        })

        return True
    
    def action_done(self):
        self.ensure_one()
        return self.write({'state': 'done'})

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
            'name': _("cheque Operations"),
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

    @api.depends('payment_method_line_id.code', 'payment_id.partner_id', 'issuer_partner_id')
    def _compute_bank_id(self):
        new_cheques = self.filtered(lambda x: x.payment_method_line_id.code == 'cheque_incoming')
        for rec in new_cheques:
            # Use issuer partner if set, otherwise use payment partner
            partner = rec.issuer_partner_id if rec.issuer_partner_id else rec.partner_id
            rec.bank_id = partner.bank_ids[:1].bank_id
        (self - new_cheques).bank_id = False

    @api.depends('payment_method_line_id.code', 'payment_id.partner_id', 'issuer_partner_id')
    def _compute_issuer_vat(self):
        new_cheques = self.filtered(lambda x: x.payment_method_line_id.code == 'cheque_incoming')
        for rec in new_cheques:
            # Use issuer partner if set, otherwise use payment partner
            partner = rec.issuer_partner_id if rec.issuer_partner_id else rec.payment_id.partner_id
            rec.issuer_vat = partner.vat
        (self - new_cheques).issuer_vat = False

    @api.onchange('issuer_vat')
    def _clean_issuer_vat(self):
        for rec in self.filtered(lambda x: x.issuer_vat and x.company_id.country_id.code):
            stdnum_vat = stdnum.util.get_cc_module(rec.company_id.country_id.code, 'vat')
            if hasattr(stdnum_vat, 'compact'):
                rec.issuer_vat = stdnum_vat.compact(rec.issuer_vat)

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
            raise UserError("Can't delete a cheque if payment is In Process!")

    def action_cash(self, bank_account_id, cashed_date):
        """
        Cash the cheque - create journal entry to move from outstanding to bank account

        :param bank_account_id: ID of the bank account to credit/debit
        :param cashed_date: Date when the cheque was cashed
        """
        self.ensure_one()

        Move = self.env['account.move']

        # Use payment's outstanding account as the clearing account
        outstanding_account = self.payment_id.outstanding_account_id
        bank_account = self.env['account.account'].browse(bank_account_id)

        if self.payment_type == 'inbound':  # incoming cheque
            credit_line = {
                'account_id': outstanding_account.id,
                'partner_id': self.partner_id.id,
                'name': self.name + '-' + 'Cashed',
                'debit': 0,
                'credit': self.amount,
                'date_maturity': self.payment_date,
            }
            debit_line = {
                'account_id': bank_account.id,
                'partner_id': self.partner_id.id,
                'name': self.name + '-' + 'Cashed',
                'debit': self.amount,
                'credit': 0,
                'date_maturity': self.payment_date,
            }
        else:  # outbound cheque
            credit_line = {
                'account_id': bank_account.id,
                'partner_id': self.partner_id.id,
                'name': self.name + '-' + 'Cashed',
                'debit': 0,
                'credit': self.amount,
                'date_maturity': self.payment_date,
            }
            debit_line = {
                'account_id': outstanding_account.id,
                'partner_id': self.partner_id.id,
                'name': self.name + '-' + 'Cashed',
                'debit': self.amount,
                'credit': 0,
                'date_maturity': self.payment_date,
            }

        move_vals = {
            'date': fields.Date.today(),
            'journal_id': self.original_journal_id.id,
            'ref': self.name,
            'line_ids': [(0, 0, credit_line), (0, 0, debit_line)]
        }
        move = Move.create(move_vals)
        move.action_post()

        # Update cheque with cashed date and done state
        self.write({'cashed_date': cashed_date, 'state': 'done'})

        return True
