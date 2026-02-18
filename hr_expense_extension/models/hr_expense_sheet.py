# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class HrExpenseSheet(models.Model):
    _inherit = 'hr.expense.sheet'

    total_amount_currency = fields.Monetary(
        string='Total Amount (TL)',
        compute='_compute_total_amount_currency',
        currency_field='currency_id',
        store=True,
        readonly=True,
    )
    untaxed_amount_currency = fields.Monetary(
        string='Untaxed Amount (TL)',
        compute='_compute_total_amount_currency',
        currency_field='currency_id',
        store=True,
        readonly=True,
    )
    total_tax_amount_currency = fields.Monetary(
        string='Taxes (TL)',
        compute='_compute_total_amount_currency',
        currency_field='currency_id',
        store=True,
        readonly=True,
    )
    currency_tl_id = fields.Many2one(
        comodel_name='res.currency',
        related='expense_line_ids.currency_id',
        string='Currency',
    )

    @api.depends('expense_line_ids.total_amount_currency', 'expense_line_ids.tax_amount_currency')
    def _compute_total_amount_currency(self):
        for sheet in self:
            sheet.total_amount_currency = sum(sheet.expense_line_ids.mapped('total_amount_currency'))
            sheet.total_tax_amount_currency = sum(sheet.expense_line_ids.mapped('tax_amount_currency'))
            sheet.untaxed_amount_currency = sheet.total_amount_currency - sheet.total_tax_amount_currency