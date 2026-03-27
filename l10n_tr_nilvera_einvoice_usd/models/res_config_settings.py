# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_tr_usd_mode = fields.Boolean(
        string='USD Mode',
        default=True,
        help='Enable USD-specific currency conversion logic in XML generation. '
             'When disabled, XML rate methods use standard behavior (no USD→TRY conversion in XML).'
    )




class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_tr_usd_mode = fields.Boolean(
        related='company_id.l10n_tr_usd_mode',
        readonly=False,
        string='USD Mode',
    )

