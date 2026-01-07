# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ChequeDepositWizard(models.TransientModel):
    _name = 'cheque.deposit.wizard'
    _description = 'Cheque Deposit Wizard'

    cheque_ids = fields.Many2many(
        'account.cheque',
        string='Cheques',
        required=True
    )

    bank_journal_id = fields.Many2one(
        'account.journal',
        string='Bank Journal',
        required=True,
        domain="[('type', '=', 'bank'), ('company_id', '=', company_id)]",
        help='Bank journal where the cheque will be deposited'
    )

    deposit_date = fields.Date(
        string='Deposit Date',
        required=True,
        default=fields.Date.context_today,
        help='Date when the cheque is deposited to the bank'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )

    cheque_count = fields.Integer(
        compute='_compute_cheque_count',
        string='Cheque Count'
    )

    total_amount = fields.Monetary(
        compute='_compute_total_amount',
        string='Total Amount',
        currency_field='currency_id'
    )

    currency_id = fields.Many2one(
        'res.currency',
        compute='_compute_currency_id',
        string='Currency'
    )

    @api.depends('cheque_ids')
    def _compute_cheque_count(self):
        for wizard in self:
            wizard.cheque_count = len(wizard.cheque_ids)

    @api.depends('cheque_ids')
    def _compute_total_amount(self):
        for wizard in self:
            wizard.total_amount = sum(wizard.cheque_ids.mapped('amount'))

    @api.depends('cheque_ids')
    def _compute_currency_id(self):
        for wizard in self:
            wizard.currency_id = wizard.cheque_ids[:1].currency_id if wizard.cheque_ids else self.env.company.currency_id

    @api.model
    def default_get(self, fields_list):
        """Pre-populate with selected cheques"""
        res = super().default_get(fields_list)

        active_ids = self.env.context.get('active_ids', [])
        active_model = self.env.context.get('active_model')

        if active_model == 'account.cheque' and active_ids:
            cheques = self.env['account.cheque'].browse(active_ids)

            # Validate all cheques can be deposited
            invalid_cheques = cheques.filtered(
                lambda c: c.payment_method_code != 'cheque_incoming' or c.state not in ['register', 'bounce']
            )

            if invalid_cheques:
                raise UserError(
                    _('The following cheques cannot be deposited:\n%s\n\n'
                      'Only incoming cheques in "Registered" or "Bounce" state can be deposited.') %
                    '\n'.join(['- %s (state: %s)' % (c.name, c.state) for c in invalid_cheques])
                )

            # Check all cheques have same currency
            currencies = cheques.mapped('currency_id')
            if len(currencies) > 1:
                raise UserError(_('All selected cheques must have the same currency.'))

            # Check all cheques belong to same company
            companies = cheques.mapped('company_id')
            if len(companies) > 1:
                raise UserError(_('All selected cheques must belong to the same company.'))

            res['cheque_ids'] = [(6, 0, cheques.ids)]
            if companies:
                res['company_id'] = companies[0].id

        return res

    def action_confirm(self):
        """Deposit the cheques to the selected bank journal"""
        self.ensure_one()

        if not self.cheque_ids:
            raise UserError(_('No cheques selected for deposit.'))

        # Validate deposit date
        if self.deposit_date > fields.Date.today():
            raise UserError(_('Deposit date cannot be in the future.'))

        # Perform deposit for each cheque
        for cheque in self.cheque_ids:
            cheque.action_deposit(
                bank_journal_id=self.bank_journal_id.id,
                deposit_date=self.deposit_date
            )

        # Success notification
        message = _('%s cheque(s) deposited successfully to %s.') % (
            len(self.cheque_ids),
            self.bank_journal_id.name
        )
        self.env['bus.bus']._sendone(
            self.env.user.partner_id,
            'simple_notification',
            {
                'type': 'success',
                'title': _('Success'),
                'message': message,
                'sticky': False,
            }
        )

        return {'type': 'ir.actions.act_window_close'}
