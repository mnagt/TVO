# -*- coding: utf-8 -*-

from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        result = super().action_confirm()
        for order in self:
            if order.partner_id and not order.partner_id.user_id and order.user_id:
                order.partner_id.user_id = order.user_id
        return result
