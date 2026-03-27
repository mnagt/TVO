import logging
from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_tr_tcmb = fields.Boolean(related='company_id.l10n_tr_tcmb')

    tcmb_rate_type = fields.Selection([
        ('rate', 'Döviz Alış'),
        ('forex_selling_rate', 'Döviz Satış'),
        ('banknote_buying_rate', 'Efektif Alış'),
        ('banknote_selling_rate', 'Efektif Satış'),
    ], string='TCMB Rate Type')

    l10n_tr_tcmb_rate = fields.Float(
        string='TCMB Rate (XML)',
        digits=(16, 4),
        help='Exchange rate from TCMB used for Turkish e-invoice XML generation',
    )



    @api.onchange('tcmb_rate_type', 'currency_id', 'invoice_date')
    def _onchange_tcmb_rate_type(self):
        """Update l10n_tr_tcmb_rate based on selected TCMB rate type."""
        if not self.is_invoice(include_receipts=True) or not self.tcmb_rate_type or not self.l10n_tr_tcmb:
            return

        company_currency = self.company_id.currency_id
        invoice_currency = self.currency_id

        # Determine which currency's rate record to look up:
        # - Same currency (e.g., USD company + USD invoice): look up TRY for the TRY/USD rate.
        # - Different currencies (e.g., TRY company + USD invoice): look up the invoice currency.
        if invoice_currency == company_currency:
            lookup_currency = self.env.ref('base.TRY')
        else:
            lookup_currency = invoice_currency

        rate_record = self.env['res.currency.rate'].search([
            ('currency_id', '=', lookup_currency.id),
            ('name', '<=', self.invoice_date or fields.Date.today()),
        ], order='name desc', limit=1)

        if not rate_record:
            return

        rate_value = getattr(rate_record, self.tcmb_rate_type, 0.0)
        if not rate_value:
            return

        # Odoo stores rates as "foreign per company" (e.g., USD per TRY for TRY company).
        # l10n_tr_tcmb_rate must store the human-readable rate: TRY per invoice currency.
        #
        # - Looked up TRY (USD company + USD invoice): rate_value = TRY per USD → already correct.
        # - Looked up invoice currency (TRY company + USD invoice): rate_value = USD per TRY → invert.
        if lookup_currency != self.env.ref('base.TRY'):
            human_rate = round(1.0 / rate_value, 6)
        else:
            human_rate = rate_value

        self.l10n_tr_tcmb_rate = human_rate
        if invoice_currency != company_currency:
            # invoice_currency_rate = how much company currency per 1 invoice currency
            # = _get_conversion_rate(invoice_currency → company_currency)
            if lookup_currency != self.env.ref('base.TRY'):
                # TRY company + foreign invoice: TRY/foreign = human_rate
                self.invoice_currency_rate = human_rate
            else:
                # Foreign company + TRY invoice: foreign/TRY = 1/human_rate
                self.invoice_currency_rate = round(1.0 / human_rate, 6)

    @api.onchange('l10n_tr_tcmb_rate')
    def _onchange_l10n_tr_tcmb_rate(self):
        if not self.l10n_tr_tcmb or not self.l10n_tr_tcmb_rate or self.currency_id == self.company_id.currency_id:
            return
        # l10n_tr_tcmb_rate = human rate = TRY per invoice_currency.
        # invoice_currency_rate = Odoo internal = invoice_currency per company_currency.
        #
        # - TRY company + USD invoice: invoice_currency_rate = TRY per USD = human_rate
        # - USD company + TRY invoice: invoice_currency_rate = USD per TRY = 1 / human_rate
        if self.currency_id.name == 'TRY':
            # Foreign company + TRY invoice: foreign/TRY = 1/human_rate
            self.invoice_currency_rate = round(1.0 / self.l10n_tr_tcmb_rate, 6)
        else:
            # TRY company + foreign invoice: TRY/foreign = human_rate
            self.invoice_currency_rate = self.l10n_tr_tcmb_rate

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'tcmb_rate_type' in fields_list and self.env.company.l10n_tr_tcmb:
            move_type = self._context.get('default_move_type')
            if move_type in ('out_invoice', 'out_refund'):
                res['tcmb_rate_type'] = 'banknote_selling_rate'  # Default to 'Efektif Satış
            elif move_type in ('in_invoice', 'in_refund'):
                res['tcmb_rate_type'] = 'rate'  # Default to 'Döviz Alış'
        return res