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

    def action_post(self):
        res = super().action_post()
        for move in self:
            if move.move_type != 'entry':
                continue
            if (move.name or '').startswith('EXCH/'):
                continue
            reconciled_ids = move.line_ids.filtered('reconciled').ids
            if not reconciled_ids:
                continue
            cheques = self.env['account.cheque'].search([
                ('outstanding_line_id', 'in', reconciled_ids),
                ('state', 'in', ['register', 'deposit']),
            ])
            for cheque in cheques:
                old_account = cheque.outstanding_line_id.account_id
                new_line = move.line_ids.filtered(
                    lambda l: l.account_id == old_account
                    and not l.reconciled
                    and l.amount_residual != 0
                )[:1]
                if new_line:
                    cheque.outstanding_line_id = new_line.id
        return res
