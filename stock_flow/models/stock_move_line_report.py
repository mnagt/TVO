# -*- coding: utf-8 -*-

from odoo import api, fields, models


class StockProductFlowReport(models.Model):
    _name = 'stock.product.flow.report'
    _description = 'Stock Move Line Report'
    _auto = False
    _rec_name = 'move_line_id'
    _order = 'date asc'

    move_line_id = fields.Many2one('stock.move.line', string="Original Move Line")
    product_id = fields.Many2one('product.product', string="Product")
    date = fields.Datetime(string="Date")
    location_id = fields.Many2one('stock.location', string="Source Location")
    location_dest_id = fields.Many2one('stock.location', string="Destination Location")
    warehouse_id = fields.Many2one('stock.warehouse', string="Warehouse")
    qty_done = fields.Float(string="Qty Done")
    signed_qty_done = fields.Float(string="Signed Qty")
    operation = fields.Char(string="Operation")
    direction = fields.Selection([('in', 'In'), ('out', 'Out')], string="Direction")
    stock_balance = fields.Float(string="Stock Balance", readonly=True, group_operator=False)
    company_id = fields.Many2one('res.company', string="Company", readonly=True)
    categ_id = fields.Many2one('product.category', string="Product Category")







    @api.model
    def init(self):
        """Initialize the stock product flow report materialized view."""
        self._drop_existing_view()
        self._create_materialized_view()
        self._create_indexes()

    def _drop_existing_view(self):
        """Drop the existing materialized view if it exists."""
        self.env.cr.execute(f"""
            DROP MATERIALIZED VIEW IF EXISTS {self._table} CASCADE
        """)

    def _get_base_query(self):
        """Get the base query with all JOINs, exposing clean aliases."""
        return """
            SELECT
                sml.id,
                sml.product_id,
                sml.date,
                sml.location_id,
                sml.location_dest_id,
                sml.quantity,
                sm.name         AS move_name,
                sl.usage        AS src_usage,
                sld.usage       AS dst_usage,
                pt.categ_id,
                sw_out.id       AS out_warehouse_id,
                sw_out.company_id AS out_company_id,
                sw_in.id        AS in_warehouse_id,
                sw_in.company_id  AS in_company_id
            FROM stock_move_line sml
            JOIN stock_move sm          ON sm.id  = sml.move_id
            JOIN product_product pp     ON pp.id  = sml.product_id
            JOIN product_template pt    ON pt.id  = pp.product_tmpl_id
            LEFT JOIN stock_location sl  ON sl.id  = sml.location_id
            LEFT JOIN stock_location sld ON sld.id = sml.location_dest_id
            LEFT JOIN stock_location l_out ON l_out.id = sml.location_id
            LEFT JOIN stock_warehouse sw_out ON
                sw_out.view_location_id = l_out.id OR
                l_out.parent_path LIKE CONCAT('%/', sw_out.view_location_id::text, '/%')
            LEFT JOIN stock_location l_in ON l_in.id = sml.location_dest_id
            LEFT JOIN stock_warehouse sw_in ON
                sw_in.view_location_id = l_in.id OR
                l_in.parent_path LIKE CONCAT('%/', sw_in.view_location_id::text, '/%')
            WHERE sm.state = 'done'
        """

    def _create_materialized_view(self):
        """Create the main materialized view with all stock movements."""
        query = f"""
            CREATE MATERIALIZED VIEW {self._table} AS (
                WITH base AS (
                    {self._get_base_query()}
                ),
                move_lines_union AS (
                    {self._get_outbound_internal_query()}
                    UNION ALL
                    {self._get_inbound_internal_query()}
                    UNION ALL
                    {self._get_external_query()}
                )
                {self._get_final_select_with_balance()}
            )
        """
        self.env.cr.execute(query)

    def _get_outbound_internal_query(self):
        """Get the query for internal to internal transfers (outbound side)."""
        return """
            SELECT
                id * 1000        AS id,
                id               AS move_line_id,
                product_id, date, location_id, location_dest_id,
                out_warehouse_id AS warehouse_id,
                out_company_id   AS company_id,
                quantity         AS qty_done,
                -quantity        AS signed_qty_done,
                {operation_case} AS operation,
                'out'            AS direction,
                categ_id
            FROM base
            WHERE src_usage = 'internal'
              AND dst_usage = 'internal'
              AND out_company_id IS NOT NULL
        """.format(
            operation_case=self._get_operation_case_statement()
        )

    def _get_inbound_internal_query(self):
        """Get the query for internal to internal transfers (inbound side)."""
        return """
            SELECT
                id * 1000 + 1    AS id,
                id               AS move_line_id,
                product_id, date, location_id, location_dest_id,
                in_warehouse_id  AS warehouse_id,
                in_company_id    AS company_id,
                quantity         AS qty_done,
                quantity         AS signed_qty_done,
                {operation_case} AS operation,
                'in'             AS direction,
                categ_id
            FROM base
            WHERE src_usage = 'internal'
              AND dst_usage = 'internal'
              AND in_company_id IS NOT NULL
        """.format(
            operation_case=self._get_operation_case_statement()
        )

    def _get_external_query(self):
        """Get the query for external to internal transfers."""
        return """
            SELECT
                id * 1000 + 2 AS id,
                id            AS move_line_id,
                product_id, date, location_id, location_dest_id,
                CASE WHEN src_usage = 'internal' THEN out_warehouse_id
                     WHEN dst_usage = 'internal' THEN in_warehouse_id
                     ELSE NULL END AS warehouse_id,
                CASE WHEN src_usage = 'internal' THEN out_company_id
                     WHEN dst_usage = 'internal' THEN in_company_id
                     ELSE NULL END AS company_id,
                quantity      AS qty_done,
                {signed_qty_case} AS signed_qty_done,
                {operation_case}  AS operation,
                {direction_case}  AS direction,
                categ_id
            FROM base
            WHERE NOT (src_usage = 'internal' AND dst_usage = 'internal')
              AND (
                  (src_usage = 'internal' AND out_company_id IS NOT NULL) OR
                  (dst_usage = 'internal' AND in_company_id IS NOT NULL) OR
                  (src_usage != 'internal' AND dst_usage != 'internal')
              )
        """.format(
            signed_qty_case=self._get_signed_qty_case_statement(),
            operation_case=self._get_operation_case_statement(),
            direction_case=self._get_direction_case_statement()
        )

    def _get_operation_case_statement(self):
        """Get the CASE statement for determining operation type."""
        return """
            CASE
                WHEN src_usage = 'supplier' AND dst_usage = 'internal' THEN 'Buy'
                WHEN src_usage = 'internal' AND dst_usage = 'customer' THEN 'Sell'
                WHEN src_usage = 'internal' AND dst_usage = 'inventory' THEN 'Scrap & Adjustment Out'
                WHEN src_usage = 'inventory' AND dst_usage = 'internal' THEN 'Scrap & Adjustment In'
                WHEN src_usage = 'customer' AND dst_usage = 'internal' THEN 'Customer Return'
                WHEN src_usage = 'internal' AND dst_usage = 'supplier' THEN 'Vendor Return'
                WHEN src_usage = 'internal' AND dst_usage = 'internal' THEN 'Transfer'
                WHEN src_usage = 'internal' AND dst_usage = 'production' THEN 'Manufacturing Consumption'
                WHEN src_usage = 'production' AND dst_usage = 'internal' THEN 'Manufacturing Production'
                WHEN src_usage = 'supplier' AND dst_usage = 'customer' THEN 'Transit'
                WHEN src_usage = 'customer' AND dst_usage = 'supplier' THEN 'Transit Return'
                WHEN src_usage = 'transit' OR dst_usage = 'transit' THEN 'External Transfer'
                ELSE move_name
            END
        """

    def _get_signed_qty_case_statement(self):
        """Get the CASE statement for signed quantity calculation."""
        return """
            CASE
                WHEN src_usage = 'internal' THEN -quantity
                WHEN dst_usage = 'internal' THEN quantity
                WHEN src_usage = 'supplier' AND dst_usage = 'customer' THEN -quantity
                WHEN src_usage = 'customer' AND dst_usage = 'supplier' THEN quantity
                WHEN src_usage = 'internal' AND dst_usage = 'production' THEN -quantity
                WHEN src_usage = 'production' AND dst_usage = 'internal' THEN quantity
                ELSE 0
            END
        """

    def _get_direction_case_statement(self):
        """Get the CASE statement for direction determination."""
        return """
            CASE
                WHEN src_usage = 'internal' THEN 'out'
                WHEN dst_usage = 'internal' THEN 'in'
                WHEN src_usage = 'supplier' AND dst_usage = 'customer' THEN 'out'
                WHEN src_usage = 'customer' AND dst_usage = 'supplier' THEN 'in'
                WHEN src_usage = 'internal' AND dst_usage = 'production' THEN 'out'
                WHEN src_usage = 'production' AND dst_usage = 'internal' THEN 'in'
                ELSE NULL
            END
        """

    def _get_final_select_with_balance(self):
        """Get the final SELECT statement with stock balance calculation."""
        return """
            SELECT
                *,
                SUM(signed_qty_done) OVER (
                    PARTITION BY product_id, warehouse_id, company_id
                    ORDER BY date,
                            CASE WHEN direction = 'in' THEN 0 ELSE 1 END,
                            id
                ) AS stock_balance
            FROM move_lines_union
        """

    def _create_indexes(self):
        """Create indexes for the materialized view."""
        self.env.cr.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_stock_balance_by_product_warehouse_company
            ON {self._table} (product_id, warehouse_id, company_id, date)
        """)
        self.env.cr.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_stock_balance_by_company
            ON {self._table} (company_id)
        """)
        self.env.cr.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_stock_balance_by_date_company
            ON {self._table} (date, company_id)
        """)

    @api.model
    def get_stock_report_for_company(self, company_id):
        """Get stock report filtered by company."""
        self.env.cr.execute(f"""
            SELECT * FROM {self._table} 
            WHERE company_id = %s
            ORDER BY date DESC, id DESC
        """, (company_id,))
        return self.env.cr.dictfetchall()

    @api.model
    def refresh_materialized_view(self):
        """Refresh the materialized view to update data."""
        self.env.cr.execute(f"""
            REFRESH MATERIALIZED VIEW {self._table}
        """)

    @api.model
    def rebuild_materialized_view(self):
        """Completely rebuild the materialized view."""
        self.init()