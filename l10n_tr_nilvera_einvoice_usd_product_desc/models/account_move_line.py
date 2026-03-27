# -*- coding: utf-8 -*-

from odoo import api, fields, models

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    nilvera_product_desc = fields.Text(
        string="Nilvera Product Description",
        compute="_compute_nilvera_product_desc",
        store=True,
        readonly=False,
    )
    
    @api.depends("product_id", "product_id.nilvera_product_desc")
    def _compute_nilvera_product_desc(self):
        """Update product description from product template when product changes."""
        for line in self:
            if line.company_id.l10n_tr_product_desc:
                if line.product_id and line.product_id.nilvera_product_desc:
                    line.nilvera_product_desc = line.product_id.nilvera_product_desc
                elif not line.nilvera_product_desc:
                    line.nilvera_product_desc = ""
            else:
                line.nilvera_product_desc = ""
