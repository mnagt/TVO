# -*- coding: utf-8 -*-

from odoo import api, models, fields
from odoo import tools


class AccountTaxBalance(models.Model):
    _name = 'account.tax.balance'
    _description = 'Tax Balance'
    _auto = False
    _order = 'date desc, id desc'

    move_id = fields.Many2one('account.move', string='Invoice', readonly=True)
    name = fields.Char(string='Number', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Partner', readonly=True)
    date = fields.Date(string='Date', readonly=True)
    ref = fields.Char(string='Reference', readonly=True)
    amount_untaxed = fields.Monetary(
        string='Tax Excluded',
        currency_field='company_currency_id',
        readonly=True,
    )
    amount_total = fields.Monetary(
        string='Total',
        currency_field='company_currency_id',
        readonly=True,
    )
    tax_amounts = fields.Json(string='Tax Amounts', readonly=True)
    tax_amounts_try = fields.Json(string='TRY Tax Amounts', readonly=True)
    try_currency_id = fields.Many2one('res.currency', string='TRY Currency', readonly=True)
    amount_untaxed_try = fields.Monetary(
        string='Tax Excluded TRY', currency_field='try_currency_id', readonly=True)
    amount_total_try = fields.Monetary(
        string='Total TRY', currency_field='try_currency_id', readonly=True)
    move_type = fields.Selection([
        ('out_invoice', 'Customer Invoice'),
        ('out_refund', 'Customer Credit Note'),
        ('in_invoice', 'Vendor Bill'),
        ('in_refund', 'Vendor Credit Note'),
    ], string='Type', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    company_currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        readonly=True,
    )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE VIEW account_tax_balance AS (
                SELECT
                    am.id                   AS id,
                    am.id                   AS move_id,
                    am.partner_id,
                    am.invoice_date         AS date,
                    am.name,
                    am.ref,
                    ABS(am.amount_untaxed_signed)   AS amount_untaxed,
                    ABS(am.amount_total_signed)     AS amount_total,
                    am.company_id,
                    am.move_type,
                    COALESCE(
                        jsonb_object_agg(
                            aml.tax_line_id::text,
                            ABS(aml.balance)
                        ) FILTER (WHERE aml.tax_line_id IS NOT NULL),
                        '{}'::jsonb
                    ) AS tax_amounts,
                    COALESCE(
                        jsonb_object_agg(
                            aml.tax_line_id::text,
                            ABS(aml.amount_tr_currency)
                        ) FILTER (WHERE aml.tax_line_id IS NOT NULL),
                        '{}'::jsonb
                    ) AS tax_amounts_try,
                    COALESCE(
                        (SELECT SUM(ABS(aml2.amount_tr_currency))
                         FROM account_move_line aml2
                         WHERE aml2.move_id = am.id
                           AND aml2.display_type NOT IN ('tax', 'rounding', 'payment_term')),
                        0
                    ) AS amount_untaxed_try,
                    COALESCE(
                        (SELECT SUM(ABS(aml2.amount_tr_currency))
                         FROM account_move_line aml2
                         WHERE aml2.move_id = am.id
                           AND aml2.display_type NOT IN ('rounding', 'payment_term')),
                        0
                    ) AS amount_total_try,
                    (SELECT rc.id FROM res_currency rc WHERE rc.name = 'TRY' LIMIT 1)
                        AS try_currency_id
                FROM account_move am
                LEFT JOIN account_move_line aml
                    ON  aml.move_id      = am.id
                    AND aml.tax_line_id  IS NOT NULL
                    AND aml.display_type = 'tax'
                WHERE am.move_type IN ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')
                  AND am.state = 'posted'
                GROUP BY
                    am.id,
                    am.partner_id,
                    am.invoice_date,
                    am.name,
                    am.ref,
                    am.amount_untaxed_signed,
                    am.amount_total_signed,
                    am.company_id,
                    am.move_type
            )
        """)

    @api.model
    def get_used_taxes(self):
        """Return [{id, name}] for taxes used in posted invoices for current companies."""
        self.env.cr.execute("""
            SELECT DISTINCT aml.tax_line_id AS id
            FROM account_move am
            JOIN account_move_line aml
                ON  aml.move_id      = am.id
                AND aml.tax_line_id  IS NOT NULL
                AND aml.display_type = 'tax'
            WHERE am.move_type IN ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')
              AND am.state = 'posted'
              AND am.company_id = ANY(%s)
        """, [self.env.companies.ids])
        tax_ids = [row['id'] for row in self.env.cr.dictfetchall()]
        taxes = self.env['account.tax'].browse(tax_ids)
        return sorted(
            [{'id': t.id, 'name': t.name} for t in taxes],
            key=lambda x: x['name'],
        )

    @api.model
    def get_company_currency_symbol(self):
        currency = self.env.company.currency_id
        return {'symbol': currency.symbol, 'position': currency.position}

    @api.model
    def get_group_tax_aggregates(self, group_domains, use_try=False):
        """Return per-group tax sums for a list of group domains.
        Returns a list of {tax_id_str: sum} dicts, one per group in the same order.
        """
        field = 'tax_amounts_try' if use_try else 'tax_amounts'
        result = []
        for domain in group_domains:
            records = self.search(domain)
            sums = {}
            for rec in records:
                for tax_id_str, amount in (getattr(rec, field) or {}).items():
                    sums[tax_id_str] = sums.get(tax_id_str, 0) + float(amount or 0)
            result.append(sums)
        return result

    def action_open_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'views': [[False, 'form']],
            'target': 'current',
        }

    def get_formview_action(self, access_uid=None):
        # Same dual-override pattern as account_ledger_balance / account_aged_balance_summary
        self.ensure_one()
        return self.action_open_invoice()
