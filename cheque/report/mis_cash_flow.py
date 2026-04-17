from psycopg2.extensions import AsIs

from odoo import models, tools


class MisCashFlow(models.Model):
    _inherit = "mis.cash_flow"

    def init(self):
        query = """
            -- Branch 1: AML lines (original logic + exclusion of open-cheque lines)
            SELECT
                -aml.id                                     AS id,
                'move_line'                                 AS line_type,
                aml.id                                      AS move_line_id,
                aml.account_id,
                CASE WHEN aml.amount_residual > 0
                     THEN aml.amount_residual ELSE 0.0 END  AS debit,
                CASE WHEN aml.amount_residual < 0
                     THEN -aml.amount_residual ELSE 0.0 END AS credit,
                aml.reconciled,
                aml.full_reconcile_id,
                aml.partner_id,
                aml.company_id,
                aml.name,
                aml.parent_state,
                COALESCE(aml.date_maturity, aml.date)       AS date
            FROM account_move_line AS aml
            WHERE aml.parent_state != 'cancel'
              AND aml.id NOT IN (
                  SELECT outstanding_line_id
                  FROM account_cheque
                  WHERE state IN ('register', 'deposit', 'cashed')
                    AND outstanding_line_id IS NOT NULL
              )

            UNION ALL

            -- Branch 2: forecast lines (unchanged)
            SELECT
                fl.id,
                'forecast_line'                             AS line_type,
                NULL                                        AS move_line_id,
                fl.account_id,
                CASE WHEN fl.balance > 0
                     THEN fl.balance ELSE 0.0 END           AS debit,
                CASE WHEN fl.balance < 0
                     THEN -fl.balance ELSE 0.0 END          AS credit,
                NULL                                        AS reconciled,
                NULL                                        AS full_reconcile_id,
                fl.partner_id,
                fl.company_id,
                fl.name,
                'posted'                                    AS parent_state,
                fl.date
            FROM mis_cash_flow_forecast_line AS fl

            UNION ALL

            -- Branch 3: open cheques by payment_date
            SELECT
                -(c.id + 2000000000)                                    AS id,
                'move_line'                                             AS line_type,
                c.outstanding_line_id                                   AS move_line_id,
                COALESCE(ol.account_id,
                         aj.cheque_collection_account_id)               AS account_id,
                CASE WHEN c.payment_type = 'inbound'
                     THEN COALESCE(ol.debit + ol.credit, c.amount)
                     ELSE 0.0 END                                       AS debit,
                CASE WHEN c.payment_type = 'outbound'
                     THEN COALESCE(ol.debit + ol.credit, c.amount)
                     ELSE 0.0 END                                       AS credit,
                FALSE                                                   AS reconciled,
                NULL::integer                                           AS full_reconcile_id,
                ap.partner_id,
                c.company_id,
                c.name,
                'posted'                                                AS parent_state,
                c.payment_date                                          AS date
            FROM account_cheque c
            LEFT JOIN account_move_line ol ON ol.id = c.outstanding_line_id
            JOIN account_payment ap ON ap.id = c.payment_id
            JOIN account_journal aj ON aj.id = ap.journal_id
            WHERE c.state IN ('register', 'deposit')
              AND COALESCE(ol.debit + ol.credit, c.amount) > 0
        """
        tools.drop_view_if_exists(self.env.cr, self._table)
        self._cr.execute(
            "CREATE OR REPLACE VIEW %s AS (%s)", (AsIs(self._table), AsIs(query))
        )
