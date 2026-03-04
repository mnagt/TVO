from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Sales Order",
        compute="_compute_sale_order_id",
        store=True,
        index=True,
        copy=False,
    )

    @api.depends("sale_line_ids.order_id", "move_id.stock_move_id.sale_line_id.order_id")
    def _compute_sale_order_id(self):
        for line in self:
            if line.sale_line_ids:
                orders = line.sale_line_ids.mapped("order_id")
                line.sale_order_id = orders if len(orders) == 1 else False
            else:
                line.sale_order_id = line.move_id.stock_move_id.sale_line_id.order_id