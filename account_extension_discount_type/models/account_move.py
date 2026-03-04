from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _prepare_product_base_line_for_taxes_computation(self, product_line):
        if (product_line.discount_type == 'fixed'
                and self.is_invoice(include_receipts=True)
                and product_line.quantity):
            self.ensure_one()
            price_unit_adj = (product_line.price_unit
                              - product_line.discount_fixed / product_line.quantity)
            return self.env['account.tax']._prepare_base_line_for_taxes_computation(
                product_line,
                price_unit=price_unit_adj,
                quantity=product_line.quantity,
                discount=0.0,
                rate=self._get_product_base_line_currency_rate(product_line),
                sign=self.direction_sign,
                special_mode=False,
                name=product_line.name,
            )
        return super()._prepare_product_base_line_for_taxes_computation(product_line)
