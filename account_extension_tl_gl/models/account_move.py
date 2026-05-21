from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def write(self, vals):
        res = super().write(vals)
        if "l10n_tr_tcmb_rate" in vals:
            self.mapped("line_ids")._compute_amount_tr_currency()
        return res