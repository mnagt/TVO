from odoo import models, fields
from odoo.tools.sql import SQL


class ProductBalanceReport(models.Model):
    _name = 'product.balance.report'
    _description = 'Product Balance Report'
    _auto = False
    _order = 'invoice_date desc'

    move_id = fields.Many2one('account.move', string='Invoice', readonly=True)
    invoice_date = fields.Date(string='Date', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    categ_id = fields.Many2one('product.category', string='Product Category', readonly=True)
    quantity = fields.Float(string='Quantity', readonly=True, aggregator='sum')
    salesperson_id = fields.Many2one('res.users', string='Salesperson', readonly=True)
    sale_id = fields.Many2one('sale.order', string='Sale Order', readonly=True)
    type = fields.Selection([('sale', 'Sale'), ('return', 'Return')], string='Type', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)

    @property
    def _table_query(self):
        return SQL("%s %s %s", self._select(), self._from(), self._where())

    def _select(self):
        return SQL("""
            SELECT
                ROW_NUMBER() OVER (ORDER BY aml.id) AS id,
                am.id AS move_id,
                am.invoice_date,
                am.partner_id,
                aml.product_id,
                pt.categ_id,
                CASE WHEN am.move_type = 'out_refund' THEN -1 * aml.quantity ELSE aml.quantity END AS quantity,
                am.invoice_user_id AS salesperson_id,
                so.id AS sale_id,
                CASE WHEN am.move_type = 'out_refund' THEN 'return' ELSE 'sale' END AS type,
                am.company_id
        """)

    def _from(self):
        return SQL("""
            FROM account_move_line aml
            JOIN account_move am ON aml.move_id = am.id
            LEFT JOIN product_product pp ON aml.product_id = pp.id
            LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
            LEFT JOIN sale_order_line_invoice_rel rel ON rel.invoice_line_id = aml.id
            LEFT JOIN sale_order_line sol ON sol.id = rel.order_line_id
            LEFT JOIN sale_order so ON sol.order_id = so.id
        """)

    def _where(self):
        return SQL("""
            WHERE am.state = 'posted'
                AND am.move_type IN ('out_invoice', 'out_refund')
                AND aml.display_type = 'product'
                AND aml.product_id IS NOT NULL
        """)

    def action_open_move(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'views': [(False, 'form')],
            'target': 'current',
        }

    def action_open_sale_order(self):
        self.ensure_one()
        if not self.sale_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Sale Order',
                    'message': 'This invoice line is not linked to a sale order.',
                    'type': 'warning',
                },
            }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_id.id,
            'views': [(False, 'form')],
            'target': 'current',
        }
