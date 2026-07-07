# -*- coding: utf-8 -*-

from odoo import api, models, fields
from odoo import tools


class AccountTaxBalanceLine(models.Model):
    _name = 'account.tax.balance.line'
    _description = 'Tax Balance Line'
    _auto = False
    _order = 'date desc, id desc'

    move_id = fields.Many2one('account.move', string='Invoice', readonly=True)
    name = fields.Char(string='Number', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Partner', readonly=True)
    date = fields.Date(string='Date', readonly=True)
    ref = fields.Char(string='Reference', readonly=True)
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
    tax_id = fields.Many2one('account.tax', string='Tax', readonly=True)
    tax_amount = fields.Monetary(
        string='Tax Amount',
        currency_field='company_currency_id',
        readonly=True,
    )
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
    try_currency_id = fields.Many2one('res.currency', string='TRY Currency', readonly=True)
    tax_amount_try = fields.Monetary(
        string='TRY Tax Amount', currency_field='try_currency_id', readonly=True)
    amount_untaxed_try = fields.Monetary(
        string='Tax Excluded TRY', currency_field='try_currency_id', readonly=True)
    amount_total_try = fields.Monetary(
        string='Total TRY', currency_field='try_currency_id', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE VIEW account_tax_balance_line AS (
                SELECT
                    COALESCE(aml.id, -am.id)       AS id,
                    am.id                           AS move_id,
                    am.partner_id,
                    am.invoice_date                 AS date,
                    am.name,
                    am.ref,
                    ABS(am.amount_untaxed_signed)   AS amount_untaxed,
                    ABS(am.amount_total_signed)     AS amount_total,
                    am.company_id,
                    am.move_type,
                    aml.tax_line_id                 AS tax_id,
                    COALESCE(ABS(aml.balance), 0)              AS tax_amount,
                    COALESCE(ABS(aml.amount_tr_currency), 0)   AS tax_amount_try,
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
            )
        """)

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
        self.ensure_one()
        return self.action_open_invoice()
