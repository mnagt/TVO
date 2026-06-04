from odoo import fields, models


class LogisticsDeclarationType(models.Model):
    _name = 'logistics.declaration.type'
    _description = 'Declaration Type'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    active = fields.Boolean(default=True)
