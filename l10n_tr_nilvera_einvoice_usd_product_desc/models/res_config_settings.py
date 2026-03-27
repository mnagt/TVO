from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'
    
    l10n_tr_product_desc = fields.Boolean(
        string='Nilvera Product Description',
        default=True,
        help='Show Nilvera product description fields on products and invoices'
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    l10n_tr_product_desc = fields.Boolean(
        related='company_id.l10n_tr_product_desc',
        readonly=False
    )