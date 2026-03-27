# -*- coding: utf-8 -*-

from odoo import fields, models

class ProductTemplate(models.Model):
    _inherit = "product.template"

    nilvera_product_desc = fields.Text(
        string="Nilvera Product Description",
        help="Visible only when Nilvera Product Description feature is enabled for the company"
    )
