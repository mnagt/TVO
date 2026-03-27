# -*- coding: utf-8 -*-

from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _compute_tax_totals(self):
        super()._compute_tax_totals()
        try_currency = self.env.ref('base.TRY', raise_if_not_found=False)
        for move in self:
            if (move.company_id.l10n_tr_try_display and move.tax_totals and 
                move.currency_id.name != 'TRY' and move.l10n_tr_tcmb_rate and try_currency):
                rate = move.l10n_tr_tcmb_rate
                move.tax_totals['display_try_amounts'] = True
                move.tax_totals['try_currency_id'] = try_currency.id
                move.tax_totals['try_base_amount'] = try_currency.round(move.tax_totals['base_amount_currency'] * rate)
                move.tax_totals['try_tax_amount'] = try_currency.round(move.tax_totals['tax_amount_currency'] * rate)
                move.tax_totals['try_total_amount'] = try_currency.round(move.tax_totals['total_amount_currency'] * rate)
                # Per-subtotal and per-tax-group TRY amounts
                for subtotal in move.tax_totals.get('subtotals', []):
                    subtotal['try_base_amount'] = try_currency.round(subtotal['base_amount_currency'] * rate)
                    for tax_group in subtotal.get('tax_groups', []):
                        tax_group['try_tax_amount'] = try_currency.round(tax_group['tax_amount_currency'] * rate)
