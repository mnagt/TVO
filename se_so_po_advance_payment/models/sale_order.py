# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    advance_payment_ids = fields.Many2many(
        'account.payment',
        'sale_order_advance_payment_rel',
        'order_id',
        'payment_id',
        string="Advance Payments",
        copy=False
    )
    advance_payment_count = fields.Integer(compute='_compute_advance_payment_count')
    advance_journal_item_count = fields.Integer(compute='_compute_advance_journal_item_count')

    @api.depends('advance_payment_ids')
    def _compute_advance_payment_count(self):
        for order in self:
            order.advance_payment_count = len(order.advance_payment_ids)

    @api.depends('advance_payment_ids.move_id.line_ids')
    def _compute_advance_journal_item_count(self):
        for order in self:
            move_lines = order.advance_payment_ids.mapped('move_id.line_ids')
            order.advance_journal_item_count = len(move_lines)

    def action_view_advance_payments(self):
        self.ensure_one()
        return {
            'name': 'Advance Payments',
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.advance_payment_ids.ids)],
            'context': {'create': False},
        }

    def action_view_advance_journal_items(self):
        self.ensure_one()
        move_lines = self.advance_payment_ids.mapped('move_id.line_ids')
        return {
            'name': 'Journal Items',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': [('id', 'in', move_lines.ids)],
            'context': {
                'create': False,
                'search_default_posted': 1,
                'search_default_group_by_move': 1
            },
        }

    def action_open_advance_payment_wizard(self):
        self.ensure_one()
        already_paid = sum(self.advance_payment_ids.filtered(lambda p: p.state in ['posted', 'paid']).mapped('amount'))
        return {
            'name': 'Sale Advance Payment',
            'type': 'ir.actions.act_window',
            'res_model': 'advance.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_type': 'sale',
                'default_sale_order_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_currency_id': self.currency_id.id,
                'default_origin': self.name,
                'default_total_amount': self.amount_total,
                'default_paid_amount': already_paid,
                'default_amount': self.amount_total - already_paid,
            }
        }
