import logging
import math
import re

from num2words import num2words
from odoo import api, models


_logger = logging.getLogger(__name__)


class AccountEdiXmlUblTr(models.AbstractModel):
    _inherit = "account.edi.xml.ubl.tr"

    def _get_pricing_exchange_rate_vals_list(self, invoice):
        """Return exchange rate values. Falls back to super() when USD mode is off or no TCMB rate configured."""
        if not invoice.company_id.l10n_tr_usd_mode:
            return super()._get_pricing_exchange_rate_vals_list(invoice)

        tcmb_rate = getattr(invoice, 'l10n_tr_tcmb_rate', 0.0)
        if not tcmb_rate:
            # Fallback: compute standard TRY rate
            invoice_currency = invoice.currency_id
            company_currency = invoice.company_id.currency_id
            try_currency = self.env.ref('base.TRY')
            if invoice_currency == company_currency:
                # USD company + USD invoice: need USD→TRY rate
                fallback_rate = round(
                    invoice_currency._get_conversion_rate(
                        invoice_currency, try_currency,
                        invoice.company_id, invoice.invoice_date
                    ), 6
                )
                target_currency_code = 'TRY'
            else:
                return super()._get_pricing_exchange_rate_vals_list(invoice)
            return [{
                'source_currency_code': invoice_currency.name.upper(),
                'target_currency_code': target_currency_code,
                'calculation_rate': fallback_rate,
                'date': invoice.invoice_date,
            }]

        company_currency = invoice.company_id.currency_id
        invoice_currency = invoice.currency_id

        # For same-currency invoices (e.g., USD company invoicing in USD),
        # Turkish law still requires showing the TRY target.
        target_currency_code = 'TRY' if invoice_currency == company_currency else company_currency.name.upper()

        return [{
            'source_currency_code': invoice_currency.name.upper(),
            'target_currency_code': target_currency_code,
            'calculation_rate': round(tcmb_rate, 6),
            'date': invoice.invoice_date,
        }]

    def _get_try_fallback_rate(self, invoice):
        """Return TRY/invoice_currency rate for USD mode when tcmb_rate is not set.
        Returns 0.0 if not applicable."""
        if invoice.currency_id != invoice.company_id.currency_id:
            return 0.0
        try_currency = self.env.ref('base.TRY')
        return round(
            invoice.currency_id._get_conversion_rate(
                invoice.currency_id, try_currency,
                invoice.company_id, invoice.invoice_date
            ), 6
        )

    def _get_invoice_currency_exchange_rate(self, invoice):
        """Return KUR note. Falls back to standard rate when USD mode is off or no TCMB rate configured."""
        if not invoice.company_id.l10n_tr_usd_mode:
            return super()._get_invoice_currency_exchange_rate(invoice)
        tcmb_rate = getattr(invoice, 'l10n_tr_tcmb_rate', 0.0)
        if not tcmb_rate:
            tcmb_rate = self._get_try_fallback_rate(invoice)
        if not tcmb_rate:
            return super()._get_invoice_currency_exchange_rate(invoice)
        return f'KUR : {tcmb_rate:.4f} TL'


    def _export_invoice_vals(self, invoice):
        """Extend to fix TRY amount-in-words for USD-based companies."""
        vals = super()._export_invoice_vals(invoice)

        # Override to use our custom template that supports DespatchDocumentReference
        vals['InvoiceType_template'] = 'l10n_tr_nilvera_einvoice_usd.ubl_tr_usd_InvoiceType'

        correct_try_note = self._get_correct_try_note(invoice)
        if correct_try_note:
            self._replace_try_note(vals, correct_try_note)

        # Add DespatchDocumentReference data for e-despatches
        if (hasattr(invoice, 'l10n_tr_edespatch') and invoice.l10n_tr_edespatch
                and hasattr(invoice, 'l10n_tr_edespatch_picking_ids') and invoice.l10n_tr_edespatch_picking_ids):
            pickings = invoice.l10n_tr_edespatch_picking_ids.filtered(
                lambda p: p.l10n_tr_nilvera_ettn and p.date_done
            )
            if pickings:
                despatch_refs = []
                for picking in pickings:
                    despatch_refs.append({
                        'id': picking.l10n_tr_nilvera_ettn,
                        'issue_date': picking.date_done.date().isoformat(),
                    })
                vals['vals']['despatch_document_reference_list'] = despatch_refs
                _logger.info(
                    "Invoice %s: despatch_document_reference_list = %s",
                    invoice.name,
                    vals['vals'].get('despatch_document_reference_list')
                )

        return vals
    

    def _get_correct_try_note(self, invoice):
        """Compute the correct TRY amount-in-words note based on invoice currency."""
        if invoice.currency_id.name == 'USD':
            tcmb_rate = getattr(invoice, 'l10n_tr_tcmb_rate', 0.0)
            if not tcmb_rate:
                tcmb_rate = self._get_try_fallback_rate(invoice)
            if not tcmb_rate:
                return None
            try_currency = self.env.ref('base.TRY')
            try_amount = (invoice.tax_totals or {}).get('try_total_amount') or invoice.amount_total * tcmb_rate
            return self._l10n_tr_get_amount_integer_partn_text_note(try_amount, try_currency)
        elif invoice.currency_id.name == 'TRY':
            return self._l10n_tr_get_amount_integer_partn_text_note(
                invoice.amount_residual, self.env.ref('base.TRY')
            )
        return None
    

    def _replace_try_note(self, vals, correct_try_note):
        """Find and replace the TRY amount note in note_vals."""
        note_vals = vals['vals'].get('note_vals', [])
        for i, note_item in enumerate(note_vals):
            note_text = note_item.get('note', '')
            if 'TRY' in note_text and 'YALNIZ' in note_text:
                note_vals[i] = {'note': correct_try_note, 'note_attrs': {}}
                break
    
    @api.model
    def _l10n_tr_get_amount_integer_partn_text_note(self, amount, currency):

        sign = math.copysign(1.0, amount)
        amount_integer_part, amount_decimal_part = divmod(abs(amount), 1)
        raw_decimal = amount_decimal_part * 100
        amount_decimal_part = round(raw_decimal)

        text_i = self._separate_turkish_number_words(num2words(amount_integer_part * sign, lang="tr")) or 'Sifir'
        text_d = self._separate_turkish_number_words(num2words(amount_decimal_part * sign, lang="tr")) or 'Sifir'
        result = f'YALNIZ : {text_i} {currency.name} {text_d} {currency.currency_subunit_label}'.upper()
        return result
    

    def _separate_turkish_number_words(self, text):
        """Insert spaces between Turkish number components for readability."""
        pattern = r'(milyar|milyon|trilyon|yüz|bin|yirmi|otuz|kırk|elli|altmış|yetmiş|seksen|doksan|on|bir|iki|üç|dört|beş|altı|yedi|sekiz|dokuz)'
        return re.sub(pattern, r' \1', text).strip()
    
    def _get_invoice_line_item_vals(self, line, taxes_vals):
        line_item_vals = super()._get_invoice_line_item_vals(line, taxes_vals)
        nilvera_desc = getattr(line, 'nilvera_product_desc', None)
        if nilvera_desc:
            line_item_vals['name'] = nilvera_desc
            line_item_vals['description'] = nilvera_desc
        return line_item_vals