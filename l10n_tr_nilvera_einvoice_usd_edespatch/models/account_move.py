# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_tr_edespatch = fields.Boolean(related='company_id.l10n_tr_edespatch')

    l10n_tr_edespatch_picking_ids = fields.Many2many(
        'stock.picking',
        'account_move_stock_picking_edespatch_rel',
        'move_id',
        'picking_id',
        string='E-Despatch References',
        domain="[('picking_type_code', '=', 'outgoing'), ('state', '=', 'done'), ('l10n_tr_nilvera_ettn', '!=', False)]",
        help='E-despatches to reference in invoice XML DespatchDocumentReference section',
    )

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move in moves:
            if move.is_invoice(include_receipts=True) and move.l10n_tr_edespatch and not move.l10n_tr_edespatch_picking_ids:
                pickings = self._get_edespatch_pickings_from_sale_orders(move)
                if pickings:
                    move.l10n_tr_edespatch_picking_ids = pickings
        return moves

    def _get_edespatch_pickings_from_sale_orders(self, invoice):
        """Get pickings from invoice's sale orders that have ETTN."""
        pickings = self.env['stock.picking']
        if 'sale_line_ids' in invoice.invoice_line_ids._fields:
            sale_orders = invoice.invoice_line_ids.sale_line_ids.order_id
            if sale_orders:
                pickings = sale_orders.picking_ids.filtered(
                    lambda p: p.state == 'done'
                    and p.picking_type_code == 'outgoing'
                    and p.l10n_tr_nilvera_ettn
                )
        return pickings