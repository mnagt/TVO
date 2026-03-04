# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    bank_bic = fields.Char(
        related='bank_id.bic',
        string='SWIFT/BIC',
        readonly=True,
    )
