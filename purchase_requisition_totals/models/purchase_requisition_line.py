# -*- coding: utf-8 -*-
from odoo import models, fields, api


class PurchaseRequisitionLine(models.Model):
    _inherit = "purchase.requisition.line"

    partner_id = fields.Many2one(related='requisition_id.vendor_id', store=True)
    currency_id = fields.Many2one(related='requisition_id.currency_id', store=True, string='Currency', readonly=True)
    taxes_id = fields.Many2many('account.tax', string='Taxes', domain=['|', ('active', '=', False), ('active', '=', True)])
    price_subtotal = fields.Monetary(compute='_compute_amount', string='Subtotal', store=True)
    price_total = fields.Monetary(compute='_compute_amount', string='Total', store=True)
    price_tax = fields.Float(compute='_compute_amount', string='Tax', store=True)

    @api.depends('product_qty', 'price_unit', 'taxes_id')
    def _compute_amount(self):
        AccountTax = self.env['account.tax']
        for line in self:
            base_line = line._prepare_base_line_for_taxes_computation()
            AccountTax._add_tax_details_in_base_line(base_line, line.company_id)
            line.price_subtotal = base_line['tax_details']['raw_total_excluded_currency']
            line.price_total = base_line['tax_details']['raw_total_included_currency']
            line.price_tax = line.price_total - line.price_subtotal

    def _prepare_base_line_for_taxes_computation(self):
        self.ensure_one()
        return self.env['account.tax']._prepare_base_line_for_taxes_computation(
            self,
            tax_ids=self.taxes_id,
            quantity=self.product_qty,
            partner_id=self.requisition_id.vendor_id,
            currency_id=self.requisition_id.currency_id or self.requisition_id.company_id.currency_id,
        )
