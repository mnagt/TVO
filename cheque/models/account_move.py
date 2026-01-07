# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class AccountMove(models.Model):

    _inherit = 'account.move'

    def button_draft(self):
        super().button_draft()
        for move in self.filtered(lambda x: x.origin_payment_id and x.origin_payment_id._is_cheque_payment()):
            # Clear outstanding line references for all cheques when move goes to draft
            cheques = move.origin_payment_id._get_cheques()
            cheques.write({'outstanding_line_id': False})
