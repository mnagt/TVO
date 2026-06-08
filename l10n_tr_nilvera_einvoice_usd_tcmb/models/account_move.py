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

    l10n_tr_tcmb_display_currency_id = fields.Many2one(
        'res.currency',
        string='TCMB Display Currency',
        compute='_compute_tcmb_display_currency',
        help='Currency to display in TCMB rate format (always the non-TRY currency)',
    )

    @api.depends('currency_id', 'company_id.currency_id')
    def _compute_tcmb_display_currency(self):
        """Compute which currency to display in TCMB rate format.

        The rate is always human-readable "TRY per non-TRY currency" (e.g., 44.4).
        Display format: "1 [non-TRY currency] = [rate] TRY"

        Examples:
        - TRY company + USD invoice → "1 USD = 44.4 TRY" (show invoice currency)
        - USD company + TRY invoice → "1 USD = 44.4 TRY" (show company currency)
        - USD company + EUR invoice → "1 EUR = 48.5 TRY" (show invoice currency)
        """
        try_currency = self.env.ref('base.TRY', raise_if_not_found=False)
        for move in self:
            if move.currency_id and move.currency_id != try_currency:
                move.l10n_tr_tcmb_display_currency_id = move.currency_id
            else:
                move.l10n_tr_tcmb_display_currency_id = move.company_id.currency_id



    @api.onchange('tcmb_rate_type', 'currency_id', 'invoice_date')
    def _onchange_tcmb_rate_type(self):
        """Update l10n_tr_tcmb_rate based on selected TCMB rate type."""
        if not self.is_invoice(include_receipts=True) or not self.tcmb_rate_type or not self.l10n_tr_tcmb:
            return

        company_currency = self.company_id.currency_id
        invoice_currency = self.currency_id

        if invoice_currency == company_currency:
            lookup_currency = self.env.ref('base.TRY')
        else:
            lookup_currency = invoice_currency

        rate_record = self.env['res.currency.rate'].search([
            ('currency_id', '=', lookup_currency.id),
            ('company_id', '=', self.company_id.id),
            ('name', '<=', self.invoice_date or fields.Date.today()),
        ], order='name desc', limit=1)

        if not rate_record:
            return

        rate_value = getattr(rate_record, self.tcmb_rate_type, 0.0)
        if not rate_value:
            return

        if lookup_currency != self.env.ref('base.TRY'):
            human_rate = round(1.0 / rate_value, 10)
        else:
            human_rate = rate_value

        self.l10n_tr_tcmb_rate = human_rate
        if invoice_currency != company_currency:
            self.invoice_currency_rate = rate_value

    @api.onchange('l10n_tr_tcmb_rate')
    def _onchange_l10n_tr_tcmb_rate(self):
        if not self.l10n_tr_tcmb or not self.l10n_tr_tcmb_rate or self.currency_id == self.company_id.currency_id:
            return
        
        if self.currency_id.name == 'TRY':
            self.invoice_currency_rate = self.l10n_tr_tcmb_rate
        else:
            self.invoice_currency_rate = round(1.0 / self.l10n_tr_tcmb_rate, 10)

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
