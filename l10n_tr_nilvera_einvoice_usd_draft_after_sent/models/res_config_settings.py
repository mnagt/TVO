from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'
    
    l10n_tr_draft_after_sent = fields.Boolean(
        string='Allow Draft After Sent',
        default=True,
        help='Allow resetting submitted invoices to draft state'
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    l10n_tr_draft_after_sent = fields.Boolean(
        related='company_id.l10n_tr_draft_after_sent',
        readonly=False
    )