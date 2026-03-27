# -*- coding: utf-8 -*-

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    l10n_tr_product_desc = fields.Boolean(
        related='company_id.l10n_tr_product_desc',
        readonly=False,
        help='Show/hide product description column in invoice lines'
    )
