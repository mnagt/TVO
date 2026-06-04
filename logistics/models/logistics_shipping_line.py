from odoo import fields, models


class LogisticsShippingLine(models.Model):
    _name = 'logistics.shipping.line'
    _description = 'Shipping Line'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    active = fields.Boolean(default=True)