from odoo import models, fields
from odoo.tools.sql import SQL


class VendorBillReport(models.Model):
    _name = 'vendor.bill.report'
    _description = 'Vendor Bill Report'
    _auto = False

    invoice_id = fields.Many2one('account.move', string='Vendor Bill', readonly=True)
    invoice_date = fields.Date(string='Invoice Date', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Vendor', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    categ_id = fields.Many2one('product.category', string='Product Category', readonly=True)
    quantity = fields.Float(string='Quantity', readonly=True)
    price_unit = fields.Float(string='Unit Price', readonly=True)
    purchase_id = fields.Many2one('purchase.order', string='Purchase Order', readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    currency_rate = fields.Float(string='Currency Rate', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)

    @property
    def _table_query(self):
        return SQL("%s %s %s", self._select(), self._from(), self._where())

    def _select(self):
        return SQL("""
            SELECT
                ROW_NUMBER() OVER (ORDER BY aml.id) AS id,
                am.id AS invoice_id,
                am.invoice_date,
                am.partner_id,
                aml.product_id,
                pt.categ_id,
                aml.quantity,
                aml.price_unit,
                am.currency_id,
                COALESCE(po.currency_rate, 1.0) AS currency_rate,
                po.id AS purchase_id,
                sw.id AS warehouse_id,
                am.company_id
        """)

    def _from(self):
        return SQL("""
            FROM account_move_line aml
            JOIN account_move am ON aml.move_id = am.id
            LEFT JOIN product_product pp ON aml.product_id = pp.id
            LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
            LEFT JOIN purchase_order_line pol ON aml.purchase_line_id = pol.id
            LEFT JOIN purchase_order po ON pol.order_id = po.id
            LEFT JOIN stock_picking_type spt ON po.picking_type_id = spt.id
            LEFT JOIN stock_warehouse sw ON spt.warehouse_id = sw.id
        """)

    def _where(self):
        return SQL("""
            WHERE am.move_type = 'in_invoice'
                AND aml.product_id IS NOT NULL
                AND am.state = 'posted'
        """)


class CustomerInvoiceReport(models.Model):
    _name = 'customer.invoice.report'
    _description = 'Customer Invoice Report'
    _auto = False

    invoice_id = fields.Many2one('account.move', string='Customer Invoice', readonly=True)
    invoice_date = fields.Date(string='Invoice Date', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    categ_id = fields.Many2one('product.category', string='Product Category', readonly=True)
    quantity = fields.Float(string='Quantity', readonly=True)
    price_unit = fields.Float(string='Unit Price', readonly=True)
    sale_id = fields.Many2one('sale.order', string='Sale Order', readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    currency_rate = fields.Float(string='Currency Rate', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)

    @property
    def _table_query(self):
        return SQL("%s %s %s", self._select(), self._from(), self._where())

    def _select(self):
        return SQL("""
            SELECT
                ROW_NUMBER() OVER (ORDER BY aml.id) AS id,
                am.id AS invoice_id,
                am.invoice_date,
                am.partner_id,
                aml.product_id,
                pt.categ_id,
                aml.quantity,
                aml.price_unit,
                am.currency_id,
                COALESCE(so.currency_rate, 1.0) AS currency_rate,
                so.id AS sale_id,
                sw.id AS warehouse_id,
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
            LEFT JOIN stock_warehouse sw ON so.warehouse_id = sw.id
        """)

    def _where(self):
        return SQL("""
            WHERE am.move_type = 'out_invoice'
                AND aml.product_id IS NOT NULL
                AND am.partner_id IS NOT NULL
                AND am.state = 'posted'
        """)
