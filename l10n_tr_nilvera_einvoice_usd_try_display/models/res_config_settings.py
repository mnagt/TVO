from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'
    
    l10n_tr_try_display = fields.Boolean(
        string='Display TRY Amounts',
        default=True,
        help='Display Turkish Lira (TRY) amounts alongside foreign currency amounts in invoices'
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    l10n_tr_try_display = fields.Boolean(
        related='company_id.l10n_tr_try_display',
        readonly=False
    )