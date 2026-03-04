# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.tools import is_html_empty
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    bank_account_ids = fields.Many2many(
        comodel_name='res.partner.bank',
        relation='sale_order_bank_account_rel',
        column1='sale_order_id',
        column2='bank_account_id',
        string='Bank Accounts',
        domain="[('partner_id', '=', company_partner_id)]",
        help='Select bank accounts to display on quotations and proforma invoices',
    )
    company_partner_id = fields.Many2one('res.partner',
        related='company_id.partner_id',
        string='Company Partner',
    )


    @api.depends('partner_id', 'amount_total', 'currency_id', 'date_order')
    def _compute_note(self):
        use_invoice_terms = self.env['ir.config_parameter'].sudo().get_param('account.use_invoice_terms')
        if not use_invoice_terms:
            return
        for order in self:
            order = order.with_company(order.company_id)
            note_content = []

            # Add partner state if exists
            if order.partner_id.state_id:
                note_content.append(f"<b>İş Ortagı Şehri:</b> {order.partner_id.state_id.name}")

            # Add USD to TRY exchange rate (using TCMB Efektif Satış / BanknoteSelling)
            Currency = self.env['res.currency']
            CurrencyRate = self.env['res.currency.rate']
            usd = Currency.search([('name', '=', 'USD')], limit=1)
            try_currency = Currency.search([('name', '=', 'TRY')], limit=1)
            if usd and try_currency:
                order_date = order.date_order.date() if order.date_order else fields.Date.today()

                # Get the currency rate record
                # If company currency is USD, look for TRY rate (stores USD->TRY rate)
                # If company currency is TRY, look for USD rate
                if order.company_id.currency_id == usd:
                    rate_record = CurrencyRate.search([
                        ('currency_id', '=', try_currency.id),
                        ('company_id', '=', order.company_id.id),
                        ('name', '<=', order_date),
                    ], order='name desc', limit=1)
                else:
                    rate_record = CurrencyRate.search([
                        ('currency_id', '=', usd.id),
                        ('company_id', '=', order.company_id.id),
                        ('name', '<=', order_date),
                    ], order='name desc', limit=1)

                # Use banknote_selling_rate if available, otherwise fall back to regular rate
                if rate_record and rate_record.banknote_selling_rate:
                    banknote_rate = rate_record.banknote_selling_rate
                    note_content.append(f"<b>Döviz Kuru:</b> {banknote_rate:,.4f}")

                    # Calculate total in TRY using banknote selling rate
                    if order.currency_id == usd:
                        total_in_try = order.amount_total * banknote_rate
                    else:
                        # For other currencies, convert to TRY using standard conversion
                        total_in_try = order.currency_id._convert(
                            order.amount_total,
                            try_currency,
                            order.company_id,
                            order_date,
                            round=False
                        )
                    note_content.append(f"<b>TL Toplamı:</b> {total_in_try:,.2f}")
                else:
                    # Fallback to standard rate if banknote_selling_rate not available
                    rate = usd._convert(
                        1.0,
                        try_currency,
                        order.company_id,
                        order_date,
                        round=False
                    )
                    note_content.append(f"<b>Döviz Kuru:</b> {rate:,.4f}")

                    total_in_try = order.currency_id._convert(
                        order.amount_total,
                        try_currency,
                        order.company_id,
                        order_date,
                        round=False
                    )
                    note_content.append(f"<b>TRY Toplamı:</b> {total_in_try:,.2f}")

            # Static disclaimer lines
            note_content.append("<hr/>")
            note_content.append("<b>1. Proforma 24 saat geçerlidir.</b>")
            note_content.append("<b>2. Döviz kuru, ödeme anında TCMB efektif satış kuru üzerinden hesaplanacaktır.</b>")
            note_content.append("<b>3. TCMB döviz kuru saat 15:30'da güncellenir. Bunu dikkate alarak ödeme yapmanızı rica ederiz.</b>")

            # Removed the HTML terms with link section
            # Only use plain text terms
            if not is_html_empty(self.env.company.invoice_terms):
                if order.partner_id.lang:
                    order = order.with_context(lang=order.partner_id.lang)
                note_content.append(order.env.company.invoice_terms)

            order.note = '<br/>'.join(note_content) if note_content else False


    def _prepare_invoice(self):
      invoice_vals = super()._prepare_invoice()  # Get the original dict from parent
      invoice_vals.pop('narration', None)         # Remove 'narration' key if it exists
      return invoice_vals