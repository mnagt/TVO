# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.tools import float_round
from odoo import tools

from ..constants import ReportConstants


class AccountAgedBalanceLine(models.Model):
    _name = 'account.aged.balance.line'
    _description = 'Aged Balance Line'
    _auto = False
    _order = 'date_maturity asc, date asc, id asc'

    # -------------------------------------------------------------------------
    # Reused Fields (copy exactly from existing model)
    # -------------------------------------------------------------------------
    date = fields.Date(string='Date', readonly=True)
    move_id = fields.Many2one('account.move', string='Reference', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Partner', readonly=True)
    account_id = fields.Many2one('account.account', string='Account', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Original Currency', readonly=True)
    company_currency_id = fields.Many2one('res.currency', string='Company Currency', readonly=True)
    reference = fields.Char(string="Reference", readonly=True)
    note = fields.Char(string="Note", readonly=True)
    type_key = fields.Char(string='Type Key', readonly=True)
    type = fields.Char(string='Type', compute='_compute_type_display', store=False)
    line_type = fields.Selection(
        [('summary', 'Summary'), ('product', 'Product')],
        string='Line Type', readonly=True
    )
    line_sort = fields.Integer(string='Line Sort', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_uom_id = fields.Many2one('uom.uom', string='UoM', readonly=True)
    quantity = fields.Float(string='Quantity', readonly=True)
    price_unit = fields.Float(string='Unit Price', readonly=True)
    discount = fields.Float(string='Discount (%)', readonly=True)
    price_subtotal = fields.Monetary(string='Subtotal', readonly=True, currency_field='currency_id')
    price_total = fields.Monetary(string='Total', readonly=True, currency_field='currency_id')
    tax_amount = fields.Monetary(string='Tax', readonly=True, currency_field='currency_id')

    # -------------------------------------------------------------------------
    # New Fields (aged balance specific)
    # -------------------------------------------------------------------------
    date_maturity = fields.Date(string='Due Date', readonly=True)
    amount_residual = fields.Monetary(string='Residual Amount', readonly=True, currency_field='company_currency_id')
    amount_residual_currency = fields.Monetary(
        string='Residual in Original Currency', readonly=True,
        currency_field='currency_id')
    days_overdue = fields.Integer(string='Days Overdue', readonly=True)
    bucket = fields.Char(string='Bucket', readonly=True)
    bucket_display = fields.Char(string='Bucket Display', compute='_compute_bucket_display', store=False)

    # -------------------------------------------------------------------------
    # TRY Fields (Phase 5, declare now with placeholder)
    # -------------------------------------------------------------------------
    tr_currency_id = fields.Many2one('res.currency', string='TRY Currency', compute='_compute_tr_currency_id')
    amount_residual_try = fields.Monetary(string='TRY Residual', readonly=True, currency_field='tr_currency_id')
    tr_rate_display = fields.Char(string='Rate', compute='_compute_tr_rate_display')

    # -------------------------------------------------------------------------
    # Computed Methods — Copy exactly from account_move_line_report.py
    # -------------------------------------------------------------------------

    def _get_try_currency(self):
        """Return the TRY res.currency record (cached per-environment)."""
        if not hasattr(self.env, '_try_currency_cache'):
            self.env._try_currency_cache = self.env['res.currency'].search(
                [('name', '=', ReportConstants.CURRENCY_TRY)], limit=1
            )
        return self.env._try_currency_cache

    @api.depends()
    def _compute_tr_currency_id(self):
        """Always return TRY currency for monetary field formatting."""
        try_currency = self._get_try_currency()
        for rec in self:
            rec.tr_currency_id = try_currency

    @api.depends('type_key')
    def _compute_type_display(self):
        type_translations = {
            'out_invoice': _('Invoice'),
            'in_invoice': _('Bill'),
            'out_refund': _('Credit Note'),
            'in_refund': _('Credit Note'),
            'bank_payment': _('Bank Payment'),
            'check_payment': _('Check'),
            'purchase': _('Purchase'),
            'sale': _('Sale'),
            'journal_entry': _('Journal Entry'),
            'product_detail': _('Product'),
        }
        for rec in self:
            rec.type = type_translations.get(rec.type_key, rec.type_key)

    # -------------------------------------------------------------------------
    # New Computed Method
    # -------------------------------------------------------------------------

    BUCKET_LABELS = {
        'current': 'Current',
        '1_30':    '1-30 Days',
        '31_60':   '31-60 Days',
        '61_90':   '61-90 Days',
        '91_120':  '91-120 Days',
        'older':   '> 120 Days',
    }

    @api.depends('bucket')
    def _compute_bucket_display(self):
        for rec in self:
            rec.bucket_display = self.BUCKET_LABELS.get(rec.bucket, rec.bucket or '')

    @api.depends('currency_id', 'amount_residual', 'amount_residual_currency', 'date', 'company_id', 'move_id')
    def _compute_tr_rate_display(self):
        """Compute rate display string for TRY view. amount_residual_try is SQL-stored."""
        try_currency = self._get_try_currency()
        has_tcmb_rate = 'l10n_tr_tcmb_rate' in self.env['account.move']._fields

        summary_recs = self.filtered(lambda r: r.line_type != 'product')
        for rec in self.filtered(lambda r: r.line_type == 'product'):
            rec.tr_rate_display = ""

        # Batch-fetch fallback rates
        rate_lookup_keys = set()
        for rec in summary_recs:
            if rec.currency_id and rec.date and rec.company_id:
                tcmb_rate = rec.move_id.l10n_tr_tcmb_rate if has_tcmb_rate and rec.move_id else 0.0
                if not tcmb_rate:
                    rate_lookup_keys.add((rec.company_id.id, str(rec.date)))

        rate_cache = {}
        if rate_lookup_keys and try_currency:
            values_list = ", ".join(
                self.env.cr.mogrify("(%s, %s::date)", (cid, dt)).decode()
                for cid, dt in rate_lookup_keys
            )
            self.env.cr.execute(f"""
                SELECT v.company_id, v.dt, r.rate
                FROM (VALUES {values_list}) AS v(company_id, dt)
                LEFT JOIN LATERAL (
                    SELECT rate FROM res_currency_rate
                    WHERE currency_id = %s AND company_id = v.company_id AND name <= v.dt
                    ORDER BY name DESC LIMIT 1
                ) r ON TRUE
            """, (try_currency.id,))
            for company_id, dt, rate in self.env.cr.fetchall():
                rate_cache[(company_id, str(dt))] = rate or 0.0

        for rec in summary_recs:
            if not rec.currency_id:
                rec.tr_rate_display = "N/A"
                continue
            tcmb_rate = rec.move_id.l10n_tr_tcmb_rate if has_tcmb_rate and rec.move_id else 0.0
            if tcmb_rate:
                rec.tr_rate_display = f"{tcmb_rate:.4f}"
            else:
                cached_rate = rate_cache.get((rec.company_id.id, str(rec.date)), 0.0)
                rec.tr_rate_display = f"{cached_rate:.4f}" if cached_rate else "0.0000"

    # -------------------------------------------------------------------------
    # Database View
    # -------------------------------------------------------------------------

    def init(self):
        """Initialize the aged balance view"""
        tools.drop_view_if_exists(self.env.cr, self._table)
        has_tcmb = 'l10n_tr_tcmb_rate' in self.env['account.move']._fields
        tcmb_expr = 'COALESCE(am.l10n_tr_tcmb_rate, 0)' if has_tcmb else '0::numeric'
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW account_aged_balance_line AS (
                WITH check_aggregates AS (
                    SELECT ap.id as payment_id,
                        string_agg(DISTINCT ac.name::text, ', ' ORDER BY ac.name::text) as check_numbers
                    FROM account_payment ap
                    JOIN account_cheque ac ON ac.payment_id = ap.id
                    GROUP BY ap.id
                )

                -- Summary SELECT (open receivable/payable lines only)
                SELECT
                    aml.id,
                    am.date AS date,
                    aml.move_id,
                    aml.partner_id,
                    aml.account_id,
                    aml.company_id,
                    aml.currency_id,
                    rc.id AS company_currency_id,
                    aml.date_maturity,
                    -- reference: same CASE as existing ledger view
                    CASE
                        WHEN aj.type = 'cash' AND ca.check_numbers IS NOT NULL THEN ca.check_numbers
                        WHEN aj.type = 'bank' AND aml.ref IS NOT NULL THEN aml.ref
                        ELSE am.name
                    END AS reference,
                    aml.name AS note,
                    -- type_key: same CASE as existing ledger view
                    CASE
                        WHEN am.move_type = 'out_invoice' THEN 'out_invoice'
                        WHEN am.move_type = 'in_invoice'  THEN 'in_invoice'
                        WHEN am.move_type = 'out_refund'  THEN 'out_refund'
                        WHEN am.move_type = 'in_refund'   THEN 'in_refund'
                        WHEN aj.type = 'bank'             THEN 'bank_payment'
                        WHEN aj.type = 'cash'             THEN 'check_payment'
                        WHEN aj.type = 'purchase'         THEN 'purchase'
                        WHEN aj.type = 'sale'             THEN 'sale'
                        ELSE 'journal_entry'
                    END AS type_key,
                    aml.amount_residual,
                    aml.amount_residual_currency,
                    -- amount_residual_try: TRY-converted residual (stored for group aggregation)
                    CASE
                        WHEN aml.currency_id = try_cur.id
                            THEN aml.amount_residual_currency
                        WHEN {tcmb_expr} > 0
                            THEN aml.amount_residual * {tcmb_expr}
                        ELSE
                            aml.amount_residual * COALESCE(try_rate.rate, 0)
                    END AS amount_residual_try,
                    -- days overdue: 0 if not yet due
                    GREATEST(0, CURRENT_DATE - COALESCE(aml.date_maturity, CURRENT_DATE)) AS days_overdue,
                    -- bucket
                    CASE
                        WHEN aml.date_maturity IS NULL
                          OR CURRENT_DATE <= aml.date_maturity                        THEN 'current'
                        WHEN CURRENT_DATE - aml.date_maturity <= 30                   THEN '1_30'
                        WHEN CURRENT_DATE - aml.date_maturity <= 60                   THEN '31_60'
                        WHEN CURRENT_DATE - aml.date_maturity <= 90                   THEN '61_90'
                        WHEN CURRENT_DATE - aml.date_maturity <= 120                  THEN '91_120'
                        ELSE                                                               'older'
                    END AS bucket,
                    NULL::integer AS product_id,
                    NULL::integer AS product_uom_id,
                    NULL::numeric AS quantity,
                    NULL::numeric AS price_unit,
                    NULL::numeric AS discount,
                    NULL::numeric AS price_subtotal,
                    NULL::numeric AS price_total,
                    NULL::numeric AS tax_amount,
                    0             AS line_sort,
                    'summary'     AS line_type
                FROM account_move_line aml
                JOIN account_move     am  ON am.id  = aml.move_id
                JOIN account_journal  aj  ON aj.id  = am.journal_id
                JOIN account_account  aa  ON aa.id  = aml.account_id
                JOIN res_company      comp ON comp.id = aml.company_id
                JOIN res_currency     rc  ON rc.id  = comp.currency_id
                JOIN res_currency try_cur ON try_cur.name = 'TRY'
                LEFT JOIN LATERAL (
                    SELECT rate FROM res_currency_rate r
                    WHERE r.currency_id = try_cur.id
                      AND r.company_id = aml.company_id
                      AND r.name <= am.date
                    ORDER BY r.name DESC LIMIT 1
                ) try_rate ON TRUE
                LEFT JOIN account_payment    ap  ON ap.move_id  = am.id
                LEFT JOIN check_aggregates   ca  ON ca.payment_id = ap.id
                WHERE am.state = 'posted'
                AND aa.account_type IN ('asset_receivable', 'liability_payable')
                AND aml.reconciled = FALSE
                AND aml.partner_id IS NOT NULL
                AND aml.amount_residual != 0

                UNION ALL

                -- Product detail lines (copy from existing, filtered to open invoices only)
                SELECT
                    aml.id,
                    am.date,
                    aml.move_id,
                    aml.partner_id,
                    aml.account_id,
                    aml.company_id,
                    aml.currency_id,
                    rc.id AS company_currency_id,
                    NULL::date    AS date_maturity,
                    am.name       AS reference,
                    aml.name      AS note,
                    'product_detail' AS type_key,
                    0::numeric    AS amount_residual,
                    0::numeric    AS amount_residual_currency,
                    0::numeric AS amount_residual_try,
                    0             AS days_overdue,
                    'current'     AS bucket,
                    aml.product_id,
                    aml.product_uom_id,
                    aml.quantity,
                    aml.price_unit,
                    aml.discount,
                    aml.price_subtotal,
                    aml.price_total,
                    (aml.price_total - aml.price_subtotal) AS tax_amount,
                    1             AS line_sort,
                    'product'     AS line_type
                FROM account_move_line aml
                JOIN account_move  am   ON am.id   = aml.move_id
                JOIN res_company   comp ON comp.id = aml.company_id
                JOIN res_currency  rc   ON rc.id   = comp.currency_id
                WHERE am.state = 'posted'
                AND aml.display_type = 'product'
                AND am.move_type IN ('out_invoice','in_invoice','out_refund','in_refund')
                AND aml.partner_id IS NOT NULL
                -- Only for invoices that have at least one open summary line
                AND am.id IN (
                    SELECT DISTINCT aml2.move_id
                    FROM account_move_line aml2
                    JOIN account_account aa2 ON aa2.id = aml2.account_id
                    WHERE aml2.reconciled = FALSE
                    AND aa2.account_type IN ('asset_receivable', 'liability_payable')
                    AND aml2.amount_residual != 0
                )
            )
        """)