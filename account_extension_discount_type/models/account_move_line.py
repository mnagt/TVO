from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    discount_type = fields.Selection(
        selection=[('percentage', 'Percentage (%)'), ('fixed', 'Fixed Amount')],
        string='Discount Type',
        default='percentage',
        required=True,
    )
    discount_fixed = fields.Monetary(
        string='Discount (Fixed)',
        currency_field='currency_id',
        default=0.0,
    )
    discount = fields.Float(
        compute='_compute_effective_discount',
        store=True,
        readonly=False,
    )

    @api.depends('discount_type', 'discount_fixed', 'price_unit', 'quantity')
    def _compute_effective_discount(self):
        for line in self:
            if line.discount_type != 'fixed':
                continue  # percentage mode: user controls discount directly
            price_total = line.price_unit * line.quantity
            if price_total:
                line.discount = min((line.discount_fixed / price_total) * 100, 100.0)
            else:
                line.discount = 0.0
