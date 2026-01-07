# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ChequeStateOption(models.Model):
    _name = 'cheque.state.option'
    _description = 'Cheque State Option'
    _order = 'sequence, id'

    name = fields.Char(string='State Name', required=True, translate=True)
    code = fields.Char(string='Technical Code', required=True)
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'State code must be unique!')
    ]
