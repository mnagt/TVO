# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_tr_tcmb_try_rate = fields.Float(
        string='TRY Rate',
        digits=(12, 6),
        help='TRY exchange rate for this invoice (units of TRY per 1 unit of invoice currency). '
             'Used in TRY reports (partner balance, GL TL). '
             'Leave 0 to auto-compute from daily rates.',
    )

    l10n_tr_is_third_currency = fields.Boolean(
        compute='_compute_l10n_tr_is_third_currency',
        store=False,
    )

    @api.depends('currency_id', 'company_id')
    def _compute_l10n_tr_is_third_currency(self):
        try_currency = self.env['res.currency'].with_context(active_test=False).search(
            [('name', '=', 'TRY')], limit=1
        )
        for rec in self:
            company_currency = rec.company_id.currency_id
            rec.l10n_tr_is_third_currency = bool(
                rec.currency_id
                and rec.currency_id != company_currency
                and (not try_currency or rec.currency_id != try_currency)
            )
