from odoo import fields, models

class ResCompany(models.Model):
    _inherit = 'res.company'
    l10n_tr_edespatch = fields.Boolean(string='E-Despatch', default=False,
        help='Enable e-despatch picking field and XML references')

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    l10n_tr_edespatch = fields.Boolean(related='company_id.l10n_tr_edespatch', readonly=False)