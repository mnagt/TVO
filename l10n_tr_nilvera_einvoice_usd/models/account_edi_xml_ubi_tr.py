

from odoo import _, models






class AccountEdiXmlUblTr(models.AbstractModel):
    _name = 'account.edi.xml.ubl.tr'
    _inherit = ['account.edi.xml.ubl.tr']

    

    def _get_pricing_exchange_rate_vals_list(self, invoice):
        rates = []
        company_currency = invoice.company_id.currency_id
        invoice_currency = invoice.currency_id
        try_currency = self.env['res.currency'].search([('name', '=', 'TRY')], limit=1)
        rates.append({
            'source_currency_code': invoice_currency.name.upper(),
            'target_currency_code': company_currency.name.upper(),
            'calculation_rate': round(try_currency._get_conversion_rate(
                invoice_currency,
                try_currency,
                invoice.company_id, 
                invoice.invoice_date
            ), 6),
            'date': invoice.invoice_date,
        })
        return rates
    

    def _get_invoice_currency_exchange_rate(self, invoice):
        try_currency = self.env['res.currency'].search([('name', '=', 'TRY')], limit=1)
        conversion_rate = self.env['res.currency']._get_conversion_rate(
            from_currency=invoice.currency_id,
            to_currency=try_currency,
            company=invoice.company_id,
            date=invoice.invoice_date,
        )
        return f'KUR : {conversion_rate:.6f} TL'