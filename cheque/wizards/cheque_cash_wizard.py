# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _
from odoo.exceptions import UserError


class ChequeCashWizard(models.TransientModel):
    _name = 'cheque.cash.wizard'
    _description = 'Cheque Cash Wizard'

    cheque_date = fields.Date(string='Cheque Date', required=True)
    bank_acc = fields.Many2one('account.account', string='Bank Account', required=True)

    def cash_out_submit(self):
        """Cash the cheque using the model's action_cash method"""
        cheque_id = self.env[self._context.get('active_model')].browse(
            self._context.get('active_ids')
        )
        return cheque_id.action_cash(self.bank_acc.id, self.cheque_date)