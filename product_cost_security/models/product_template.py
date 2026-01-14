# Copyright 2018 Sergio Teruel - Tecnativa <sergio.teruel@tecnativa.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models


class ProductTemplate(models.Model):
    _name = "product.template"
    _inherit = ["product.template", "product.cost.security.mixin"]
