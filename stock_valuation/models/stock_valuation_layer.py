# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, tools
from odoo.tools import float_compare, float_is_zero


class StockValuationLayer(models.Model):

    _inherit = 'stock.valuation.layer'

    warehouse_id = fields.Many2one(
        'stock.warehouse', 
        string='Warehouse', 
        readonly=True, 
        index=True,
        store=True,)

    unit_cost = fields.Float('Unit Value', digits='Product Price', readonly=False, aggregator=None)
    value = fields.Monetary('Total Value', readonly=False)
    