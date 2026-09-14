# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        res = super(AccountMove, self).action_post()
        for move in self:
            if move.move_type not in ('out_invoice', 'in_invoice'):
                continue
            sale_orders = move.line_ids.sale_line_ids.order_id
            purchase_orders = move.line_ids.purchase_line_id.order_id
            payments = self.env['account.payment']
            account_id = False
            if move.move_type == 'out_invoice' and sale_orders:
                payments = sale_orders.mapped('advance_payment_ids')
                account_id = move.partner_id.property_account_receivable_id.id
            elif move.move_type == 'in_invoice' and purchase_orders:
                payments = purchase_orders.mapped('advance_payment_ids')
                account_id = move.partner_id.property_account_payable_id.id
            if payments and account_id:
                domain = [
                    ('account_id', '=', account_id),
                    ('payment_id', 'in', payments.ids),
                    ('reconciled', '=', False)
                ]
                lines_to_reconcile = self.env['account.move.line'].search(domain)
        return res

    def js_assign_outstanding_line(self, line_id):
        res = super(AccountMove, self).js_assign_outstanding_line(line_id)
        line = self.env['account.move.line'].browse(line_id)
        if line.payment_id:
            self._link_payment_to_orders(line.payment_id)
        return res

    def _reconstruct_payment_links(self):
        for move in self:
            pay_info = move._get_reconciled_payments()
            for payment in pay_info:
                move._link_payment_to_orders(payment)

    def _link_payment_to_orders(self, payment):
        sale_orders = self.line_ids.sale_line_ids.order_id
        purchase_orders = self.line_ids.purchase_line_id.order_id

        if sale_orders:
            for order in sale_orders:
                if payment.id not in order.advance_payment_ids.ids:
                    order.write({'advance_payment_ids': [(4, payment.id)]})

        if purchase_orders:
            for order in purchase_orders:
                if payment.id not in order.advance_payment_ids.ids:
                    order.write({'advance_payment_ids': [(4, payment.id)]})

    def write(self, vals):
        res = super(AccountMove, self).write(vals)
        if 'payment_state' in vals or 'amount_residual' in vals:
            self._reconstruct_payment_links()
        return res
