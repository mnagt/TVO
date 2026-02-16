# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.tools import float_round
from odoo import tools
from collections import defaultdict


class ReportConstants:
    """Constants for account move line report."""

    # Currencies
    COMPANY_CURRENCY = 'TRY'
    USD_CURRENCY = 'USD'
    TRY_CURRENCY = 'TRY'

    # Excluded journals
    EXCLUDED_JOURNAL_CODES = ('KRFRK',)


class AccountMoveLineReport(models.Model):
    _name = 'account.move.line.report'
    _description = 'Account Move Line Report'
    _auto = False
    _order = 'date asc, reference asc, line_sort asc, id asc'

    date = fields.Date(string='Date', readonly=True)
    move_id = fields.Many2one('account.move', string='Reference', readonly=True)
    amount_currency = fields.Monetary(string='Amount Currency', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Original Currency', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Partner', readonly=True)
    account_id = fields.Many2one('account.account', string='Account', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    tr_currency_id = fields.Many2one('res.currency', string='TRY Currency', compute='_compute_tr_currency_id')
    company_currency_id = fields.Many2one('res.currency', string='Company Currency', readonly=True)

    # Enhance dta view
    reference = fields.Char(string="Reference", readonly=True)
    note = fields.Char(string="Note", readonly=True)
    type_key = fields.Char(string='Type Key', readonly=True)
    type = fields.Char(string='Type', compute='_compute_type_display', store=False)

    # For Normal Report in Company Currency
    debit = fields.Monetary(string='Debit', readonly=True, currency_field='company_currency_id')
    credit = fields.Monetary(string='Credit', readonly=True, currency_field='company_currency_id')
    balance = fields.Monetary(string='Balance', readonly=True)
    cumulated_balance = fields.Monetary(string='Cumulated Balance', compute='_compute_cumulated_balance', store=False, currency_field='company_currency_id')

    # For USD Value Report
    usd_rate_display = fields.Char('Rate Display', compute='_compute_usd_value')
    usd_value = fields.Monetary('USD Value', compute='_compute_usd_value', currency_field='currency_id')
    cumulated_usd_value = fields.Monetary('Cumulated USD Value', compute='_compute_cumulated_usd_value', currency_field='currency_id')

    # For TRY Value Report
    tr_rate_display = fields.Char('Rate', compute='_compute_amount_tr_currency')
    amount_tr_currency = fields.Monetary('TL Value', compute='_compute_amount_tr_currency', currency_field='tr_currency_id')
    cumulated_amount_tr_currency = fields.Monetary('Cumulated TL', compute='_compute_cumulated_amount_tr_currency', currency_field='tr_currency_id')
    amount_tr_debit = fields.Monetary(string='Debit', compute='_compute_amount_tr_debit_credit', currency_field='tr_currency_id', store=False)
    amount_tr_credit = fields.Monetary(string='Credit', compute='_compute_amount_tr_debit_credit', currency_field='tr_currency_id', store=False)
    
    # Line classification
    line_type = fields.Selection(
        [('summary', 'Summary'), ('product', 'Product')],
        string='Line Type', readonly=True
    )
    line_sort = fields.Integer(string='Line Sort', readonly=True)

    # Product detail fields
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_uom_id = fields.Many2one('uom.uom', string='UoM', readonly=True)
    quantity = fields.Float(string='Quantity', readonly=True)
    price_unit = fields.Float(string='Unit Price', readonly=True)
    discount = fields.Float(string='Discount (%)', readonly=True)
    price_subtotal = fields.Monetary(string='Subtotal', readonly=True, currency_field='currency_id')
    price_total = fields.Monetary(string='Total', readonly=True, currency_field='currency_id')
    tax_amount = fields.Monetary(string='Tax', readonly=True, currency_field='currency_id')
    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _get_cumulation_sort_key(self, record):
        """Standard sort key for cumulation calculations."""
        return (
            record.partner_id.id or 0,
            record.date or '',
            record.reference or '',
            record.line_sort or 0,
            record.id
        )

    def _cumulate_by_group(self, value_field, result_field, group_key_fn, initial_value_fn=None):
        grouped = {}
        for rec in sorted(self, key=self._get_cumulation_sort_key):
            if rec.line_type == 'product':
                setattr(rec, result_field, 0.0)
                continue
            key = group_key_fn(rec)
            if key not in grouped:
                grouped[key] = initial_value_fn(rec) if initial_value_fn else 0.0
            grouped[key] += getattr(rec, value_field) or 0.0
            setattr(rec, result_field, grouped[key])


    
    def _compute_tr_currency_id(self):
        """Always return TRY currency for monetary field formatting."""
        try_currency = self.env['res.currency'].search(
            [('name', '=', ReportConstants.TRY_CURRENCY)], limit=1
        )
        for rec in self:
            rec.tr_currency_id = try_currency

    # -------------------------------------------------------------------------
    # Database View
    # -------------------------------------------------------------------------

    def init(self):
        """Initialize the report view"""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW account_move_line_report AS (
                WITH check_aggregates AS (
                    SELECT ap.id as payment_id,
                        string_agg(DISTINCT ac.name::text, ', ' ORDER BY ac.name::text) as check_numbers
                    FROM account_payment ap
                    JOIN account_cheque ac ON ac.payment_id = ap.id
                    GROUP BY ap.id
                )

                -- Summary lines (receivable/payable) — existing
                SELECT
                    aml.id, aml.date, aml.move_id, aml.partner_id, aml.account_id, aml.company_id,
                    aml.debit, aml.credit, aml.balance,
                    aml.amount_currency, aml.currency_id, rc.id AS company_currency_id,
                    CASE
                        WHEN aj.type = 'cash' AND ca.check_numbers IS NOT NULL THEN
                            ca.check_numbers
                        WHEN aj.type = 'bank' AND aml.ref IS NOT NULL THEN
                            aml.ref
                        ELSE
                            am.name
                    END AS reference,

                    CASE
                        WHEN am.move_type = 'out_invoice' THEN 'out_invoice'
                        WHEN am.move_type = 'in_invoice' THEN 'in_invoice'
                        WHEN am.move_type = 'out_refund' THEN 'out_refund'
                        WHEN am.move_type = 'in_refund' THEN 'in_refund'
                        WHEN aj.type = 'bank' THEN 'bank_payment'
                        WHEN aj.type = 'cash' THEN 'check_payment'
                        WHEN aj.type = 'purchase' THEN 'purchase'
                        WHEN aj.type = 'sale' THEN 'sale'
                        ELSE 'journal_entry'
                    END AS type_key,
                    aml.name AS note,
                    NULL::integer AS product_id,
                    NULL::integer AS product_uom_id,
                    NULL::numeric AS quantity,
                    NULL::numeric AS price_unit,
                    NULL::numeric AS discount,
                    NULL::numeric AS price_subtotal,
                    NULL::numeric AS price_total,
                    NULL::numeric AS tax_amount,
                    0 AS line_sort,
                    'summary' AS line_type
                FROM account_move_line aml
                JOIN account_move am ON am.id = aml.move_id
                JOIN account_journal aj ON aj.id = am.journal_id
                JOIN account_account aa ON aa.id = aml.account_id
                JOIN res_company comp ON comp.id = aml.company_id
                JOIN res_currency rc ON rc.id = comp.currency_id
                LEFT JOIN account_payment ap ON ap.move_id = am.id
                LEFT JOIN check_aggregates ca ON ca.payment_id = ap.id
                WHERE am.state = 'posted'
                AND aa.account_type IN ('asset_receivable', 'liability_payable')
                AND aml.partner_id IS NOT NULL

                UNION ALL

                -- Product detail lines (from invoices/bills)
                SELECT
                    aml.id AS id,
                    am.date AS date,
                    aml.move_id AS move_id,
                    aml.partner_id AS partner_id,
                    aml.account_id AS account_id,
                    aml.company_id AS company_id,
                    0 AS debit,
                    0 AS credit,
                    0 AS balance,
                    0 AS amount_currency,
                    aml.currency_id AS currency_id,
                    rc.id AS company_currency_id,
                    am.name AS reference,
                    'product_detail' AS type_key,
                    aml.name AS note,
                    aml.product_id AS product_id,
                    aml.product_uom_id AS product_uom_id,
                    aml.quantity AS quantity,
                    aml.price_unit AS price_unit,
                    aml.discount AS discount,
                    aml.price_subtotal AS price_subtotal,
                    aml.price_total AS price_total,
                    (aml.price_total - aml.price_subtotal) AS tax_amount,
                    1 AS line_sort,
                    'product' AS line_type
                FROM account_move_line aml
                JOIN account_move am ON am.id = aml.move_id
                JOIN res_company comp ON comp.id = aml.company_id
                JOIN res_currency rc ON rc.id = comp.currency_id
                WHERE am.state = 'posted'
                AND aml.display_type = 'product'
                AND am.move_type IN ('out_invoice', 'in_invoice', 'out_refund', 'in_refund')
                AND aml.partner_id IS NOT NULL
            )
        """)

    
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



    @api.depends('partner_id', 'date', 'move_id', 'balance')
    @api.depends_context('date_from', 'action_name')
    def _compute_cumulated_balance(self):
        """Compute cumulated balance with inline initial balance."""
        date_from = self.env.context.get('date_from')
        initial_balances = {}

        if date_from and self:
            partners = self.mapped('partner_id')
            if partners:
                self.env.cr.execute("""
                    SELECT amlr.partner_id, SUM(amlr.debit) - SUM(amlr.credit)
                    FROM account_move_line_report amlr
                    JOIN account_move am ON am.id = amlr.move_id
                    JOIN account_journal aj ON aj.id = am.journal_id
                    WHERE amlr.date < %s
                    AND amlr.partner_id IN %s
                    AND amlr.line_type = 'summary'
                    AND aj.code NOT IN %s
                    GROUP BY amlr.partner_id
                """, (date_from, tuple(partners.ids), ReportConstants.EXCLUDED_JOURNAL_CODES))
                initial_balances = dict(self.env.cr.fetchall())

        grouped = {}
        for rec in sorted(self, key=self._get_cumulation_sort_key):
            if rec.line_type == 'product':
                rec.cumulated_balance = 0.0
                continue
            pid = rec.partner_id.id
            if pid not in grouped:
                grouped[pid] = initial_balances.get(pid, 0.0)
            grouped[pid] += rec.balance or 0.0
            rec.cumulated_balance = grouped[pid]



    @api.depends('currency_id', 'amount_currency', 'date', 'company_id')
    def _compute_usd_value(self):
        """Compute USD equivalent value for the transaction."""
        usd_currency = self.env['res.currency'].search(
            [('name', '=', ReportConstants.USD_CURRENCY)], limit=1
        )
        for rec in self:
            if rec.currency_id == usd_currency:
                rec.usd_value = rec.amount_currency
                rec.usd_rate_display = "1.0000"
            elif rec.currency_id and rec.currency_id.name == ReportConstants.COMPANY_CURRENCY:
                rate = self.env['res.currency.rate'].search([
                    ('currency_id.name', '=', ReportConstants.USD_CURRENCY),
                    ('company_id', '=', rec.company_id.id),
                    ('name', '<', rec.date)
                ], order='name desc', limit=1)
                if rate and rate.inverse_company_rate:
                    rec.usd_rate_display = f"{rate.inverse_company_rate:.4f}"
                    rec.usd_value = float_round(rec.amount_currency / rate.inverse_company_rate, precision_digits=2)
                else:
                    rec.usd_value = 0.0
                    rec.usd_rate_display = "0.0000"
            else:
                rec.usd_value = 0.0
                rec.usd_rate_display = "N/A"


    @api.depends('partner_id', 'currency_id', 'date', 'move_id', 'usd_value')
    def _compute_cumulated_usd_value(self):
        """Compute cumulative USD value, grouped by partner."""
        self._cumulate_by_group(
            value_field='usd_value',
            result_field='cumulated_usd_value',
            group_key_fn=lambda r: r.partner_id.id
        )

    @api.depends('currency_id', 'amount_currency', 'balance', 'date', 'company_id', 'move_id')
    def _compute_amount_tr_currency(self):
        """Compute TRY equivalent value for the transaction.

        - TRY document: amount_tr_currency = amount_currency (already TRY)
        - Non-TRY invoice with l10n_tr_tcmb_rate: balance × l10n_tr_tcmb_rate
        - Non-TRY other: balance × res.currency.rate for TRY
        """
        try_currency = self.env['res.currency'].search(
            [('name', '=', ReportConstants.TRY_CURRENCY)], limit=1
        )
        has_tcmb_rate = 'l10n_tr_tcmb_rate' in self.env['account.move']._fields
        for rec in self:
            if rec.line_type == 'product':
                rec.amount_tr_currency = 0.0
                rec.tr_rate_display = ""
                continue
            if rec.currency_id == try_currency:
                # Already in TRY — no conversion needed
                rec.amount_tr_currency = rec.amount_currency
                rec.tr_rate_display = "1.0000"
            elif rec.currency_id:
                # Non-TRY: check for invoice TCMB rate first
                tcmb_rate = 0.0
                if has_tcmb_rate and rec.move_id:
                    tcmb_rate = rec.move_id.l10n_tr_tcmb_rate or 0.0

                if tcmb_rate:
                    # Use the user-selected TCMB rate from the invoice
                    rec.tr_rate_display = f"{tcmb_rate:.4f}"
                    rec.amount_tr_currency = float_round(
                        rec.balance * tcmb_rate,
                        precision_digits=2
                    )
                else:
                    # Fallback: daily rate from res.currency.rate
                    rate_record = self.env['res.currency.rate'].search([
                        ('currency_id', '=', try_currency.id),
                        ('company_id', '=', rec.company_id.id),
                        ('name', '<=', rec.date)
                    ], order='name desc', limit=1)
                    if rate_record and rate_record.rate:
                        rec.tr_rate_display = f"{rate_record.rate:.4f}"
                        rec.amount_tr_currency = float_round(
                            rec.balance * rate_record.rate,
                            precision_digits=2
                        )
                    else:
                        rec.amount_tr_currency = rec.balance or 0.0
                        rec.tr_rate_display = "0.0000"
            else:
                rec.amount_tr_currency = 0.0
                rec.tr_rate_display = "N/A"

    @api.depends('partner_id', 'currency_id', 'date', 'move_id', 'amount_tr_currency')
    def _compute_cumulated_amount_tr_currency(self):
        """Compute cumulative TRY value, grouped by partner."""
        self._cumulate_by_group(
            value_field='amount_tr_currency',
            result_field='cumulated_amount_tr_currency',
            group_key_fn=lambda r: r.partner_id.id
        )

    @api.depends('amount_tr_currency')
    def _compute_amount_tr_debit_credit(self):
        """Split TRY amount into debit (positive) and credit (negative)."""
        for rec in self:
            if rec.line_type == 'product':
                rec.amount_tr_debit = 0.0
                rec.amount_tr_credit = 0.0
                continue
            rec.amount_tr_debit = rec.amount_tr_currency if rec.amount_tr_currency > 0 else 0.0
            rec.amount_tr_credit = abs(rec.amount_tr_currency) if rec.amount_tr_currency < 0 else 0.0



    def partner_details(self, partner):
        user = self.env['res.users'].browse(partner)
        login = user.login
        name = user.partner_id.name if user.partner_id else 'N/A' 
        return {
            'id': partner,
            'name': name,
            'login': login,
        }
    

    @api.model
    def get_opening_balance_value(self, partner_id, date_from):
        """Return opening balances per currency for toolbar display."""
        if not partner_id or not date_from:
            return {}

        self.env.cr.execute("""
            SELECT rc.name, SUM(amlr.debit) - SUM(amlr.credit)
            FROM account_move_line_report amlr
            JOIN account_move am ON am.id = amlr.move_id
            JOIN account_journal aj ON aj.id = am.journal_id
            JOIN res_currency rc ON rc.id = amlr.currency_id
            WHERE amlr.date < %s
            AND amlr.partner_id = %s
            AND amlr.line_type = 'summary'
            AND aj.code NOT IN %s
            GROUP BY rc.name
        """, (date_from, partner_id, ReportConstants.EXCLUDED_JOURNAL_CODES))

        result = {}
        for currency_name, balance in self.env.cr.fetchall():
            result[currency_name] = {'opening': balance}
        return result

