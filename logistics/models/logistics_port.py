from odoo import api, fields, models


class LogisticsPort(models.Model):
    _name = 'logistics.port'
    _description = 'Port'
    _order = 'name'

    name = fields.Char(string='Port Name', required=True)
    code = fields.Char(string='Port Code')
    country_id = fields.Many2one('res.country', string='Country')
    active = fields.Boolean(default=True)
    display_name = fields.Char(compute='_compute_display_name')

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Port code must be unique.'),
    ]

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for port in self:
            port.display_name = f"{port.code} - {port.name}" if port.code else port.name
