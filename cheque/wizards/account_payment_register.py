from odoo import models, fields, api, Command, _
from odoo.exceptions import ValidationError


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    new_cheque_ids = fields.One2many('payment.register.cheque', 'payment_register_id', string="New Checks")
    move_cheque_ids = fields.Many2many(
        comodel_name='account.cheque',
        string='Checks',
    )

    @api.depends('move_cheque_ids.amount', 'new_cheque_ids.amount', 'payment_method_code')
    def _compute_amount(self):
        super()._compute_amount()
        for wizard in self.filtered(lambda x: x._is_cheque_payment(check_subtype='new_check')):
            wizard.amount = sum(wizard.new_cheque_ids.mapped('amount'))
        for wizard in self.filtered(lambda x: x._is_cheque_payment(check_subtype='move_check')):
            wizard.amount = sum(wizard.move_cheque_ids.mapped('amount'))

    @api.depends('move_cheque_ids.currency_id')
    def _compute_currency_id(self):
        super()._compute_currency_id()
        for wizard in self.filtered(lambda x: x._is_cheque_payment(check_subtype='move_check')):
            if wizard.move_cheque_ids:
                wizard.currency_id = wizard.move_cheque_ids[0].currency_id

    def _is_cheque_payment(self, check_subtype=False):
        if check_subtype == 'move_check':
            codes = ['cheque_existing_in', 'cheque_existing_out', 'cheque_return']
        elif check_subtype == 'new_check':
            codes = ['cheque_incoming', 'cheque_outgoing']
        else:
            codes = ['cheque_existing_in', 'cheque_existing_out', 'cheque_return', 'cheque_incoming', 'cheque_outgoing']
        return self.payment_method_code in codes

    def _create_payment_vals_from_wizard(self, batch_result):
        vals = super()._create_payment_vals_from_wizard(batch_result)
        if self.new_cheque_ids:
            vals.update({'new_cheque_ids': [Command.create({
                'name': x.name,
                'issuer_partner_id': x.issuer_partner_id.id if x.issuer_partner_id else False,
                'bank_id': x.bank_id.id,
                'issuer_vat': x.issuer_vat,
                'payment_date': x.payment_date,
                'amount': x.amount}) for x in self.new_cheque_ids
            ]})
        if self.move_cheque_ids:
            vals.update({
                'move_cheque_ids': [Command.link(x.id) for x in self.move_cheque_ids]
            })
        return vals

    def action_create_payments(self):
        if self._is_cheque_payment(check_subtype="move_check"):
            cheque_currencies = self.move_cheque_ids.mapped("currency_id")
            if cheque_currencies and (len(cheque_currencies) > 1 or cheque_currencies != self.currency_id):
                raise ValidationError(_(
                    "You can't mix checks of different currencies in one payment, "
                    "and you can't change the payment's currency if checks are already created in that currency.\n"
                    "Please create separate payments for each currency."
                ))
        return super().action_create_payments()
