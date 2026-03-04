from odoo import api, fields, models
from odoo.tools.sql import SQL


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    tr_debit = fields.Monetary(
        string="TL Debit",
        compute="_compute_tr_debit_credit",
        currency_field="tr_currency_id",
    )

    tr_credit = fields.Monetary(
        string="TL Credit",
        compute="_compute_tr_debit_credit",
        currency_field="tr_currency_id",
    )

    cumulated_tr_balance = fields.Monetary(
        string="Cumulated TL Balance",
        compute="_compute_cumulated_tr_balance",
        currency_field="tr_currency_id",
        exportable=False,
    )

    @api.depends("amount_tr_currency")
    def _compute_tr_debit_credit(self):
        for line in self:
            val = line.amount_tr_currency or 0.0
            line.tr_debit = val if val > 0.0 else 0.0
            line.tr_credit = abs(val) if val < 0.0 else 0.0

    @api.depends_context('order_cumulated_balance', 'domain_cumulated_balance')
    def _compute_cumulated_tr_balance(self):
        if not self.env.context.get('order_cumulated_balance'):
            self.cumulated_tr_balance = 0
            return
        self.env['account.move.line'].flush_model(['amount_tr_currency'])
        query = self._where_calc(
            list(self.env.context.get('domain_cumulated_balance') or [])
        )
        sql_order = self._order_to_sql(
            self.env.context.get('order_cumulated_balance'), query, reverse=True
        )
        result = dict(self.env.execute_query(query.select(
            SQL.identifier(query.table, "id"),
            SQL(
                "SUM(%s) OVER (ORDER BY %s ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)",
                SQL.identifier(query.table, "amount_tr_currency"),
                sql_order,
            ),
        )))
        for record in self:
            record.cumulated_tr_balance = result.get(record.id, 0.0)

    def search_fetch(self, domain, field_names, offset=0, limit=None, order=None):
        # When cumulated_tr_balance is requested, inject same context as cumulated_balance
        if 'cumulated_tr_balance' in field_names and 'cumulated_balance' not in field_names:
            # Add cumulated_balance to ensure the core search_fetch override fires
            field_names = list(field_names) + ['cumulated_balance']
        return super().search_fetch(domain, field_names, offset=offset, limit=limit, order=order)