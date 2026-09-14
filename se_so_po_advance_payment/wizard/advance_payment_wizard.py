# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AdvancePaymentWizard(models.TransientModel):
    _name = 'advance.payment.wizard'
    _description = 'Advance Payment Wizard'

    order_type = fields.Selection([('sale', 'Sales'), ('purchase', 'Purchase')], string="Order Type", required=True)
    sale_order_id = fields.Many2one('sale.order', string="Sales Order")
    purchase_order_id = fields.Many2one('purchase.order', string="Purchase Order")
    partner_id = fields.Many2one('res.partner', string="Partner", required=True)

    origin = fields.Char(string="Origin", readonly=True)
    amount = fields.Monetary(string="Payment Amount", required=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string="Currency", required=True)

    total_amount = fields.Monetary(string="Total Amount", readonly=True, currency_field='currency_id')
    paid_amount = fields.Monetary(string="Paid Amount", readonly=True, currency_field='currency_id')
    payment_difference = fields.Monetary(string="Payment Difference", compute='_compute_payment_difference',
                                         currency_field='currency_id')

    payment_method_line_id = fields.Many2one('account.payment.method.line', string="Method", required=True)
    journal_id = fields.Many2one('account.journal', string="Payment (Journal)",
                                 domain="[('type', 'in', ('bank', 'cash'))]", required=True)
    payment_date = fields.Datetime(string="Payment Date", default=fields.Datetime.now, required=True)

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        if self.journal_id:
            payment_type = 'inbound' if self.order_type == 'sale' else 'outbound'
            methods = self.journal_id.inbound_payment_method_line_ids if payment_type == 'inbound' else self.journal_id.outbound_payment_method_line_ids
            if methods:
                self.payment_method_line_id = methods.id
            return {'domain': {'payment_method_line_id': [('id', 'in', methods.ids)]}}

    @api.depends('total_amount', 'paid_amount', 'amount')
    def _compute_payment_difference(self):
        for wizard in self:
            wizard.payment_difference = wizard.total_amount - wizard.paid_amount - wizard.amount

    def action_create_advance_payment(self):
        self.ensure_one()
        if self.amount <= 0:
            raise UserError(_("Payment Amount must be greater than zero."))

        payment_type = 'inbound' if self.order_type == 'sale' else 'outbound'
        partner_type = 'customer' if self.order_type == 'sale' else 'supplier'

        payment_vals = {
            'payment_type': payment_type,
            'partner_type': partner_type,
            'partner_id': self.partner_id.id,
            'amount': self.amount,
            'currency_id': self.currency_id.id,
            'journal_id': self.journal_id.id,
            'payment_method_line_id': self.payment_method_line_id.id,
            'date': self.payment_date.date(),
            'memo': self.origin,
        }

        payment = self.env['account.payment'].create(payment_vals)
        payment.action_post()

        if payment.state == 'in_process' and payment.paired_internal_transfer_payment_id:
            payment.write({'state': 'paid'})

        if self.order_type == 'sale' and self.sale_order_id:
            self.sale_order_id.write({'advance_payment_ids': [(4, payment.id)]})
        elif self.order_type == 'purchase' and self.purchase_order_id:
            self.purchase_order_id.write({'advance_payment_ids': [(4, payment.id)]})

        return {'type': 'ir.actions.act_window_close'}
