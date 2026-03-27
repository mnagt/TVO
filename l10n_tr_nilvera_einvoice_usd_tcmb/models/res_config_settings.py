from odoo import fields, models

class ResCompany(models.Model):
    _inherit = 'res.company'
    l10n_tr_tcmb = fields.Boolean(string='TCMB Rate', default=False,
        help='Show TCMB rate fields on invoices')

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    l10n_tr_tcmb = fields.Boolean(related='company_id.l10n_tr_tcmb', readonly=False)