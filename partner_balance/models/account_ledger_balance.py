# -*- coding: utf-8 -*-

from collections import defaultdict
from odoo import api, models, fields
from odoo import tools


class AccountLedgerBalance(models.Model):
    _name = 'account.ledger.balance'
    _description = 'Ledger Balance'
    _auto = False
    _order = 'partner_id'

    partner_id = fields.Many2one('res.partner', string='Partner', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    user_id = fields.Many2one('res.users', string='Salesperson', readonly=True)
    balance = fields.Monetary(string='Balance', readonly=True, currency_field='company_currency_id')
    company_currency_id = fields.Many2one(
        'res.currency', string='Currency', related='company_id.currency_id', readonly=True
    )
    balance_try = fields.Monetary(compute='_compute_balance_try', currency_field='try_currency_id')
    try_currency_id = fields.Many2one('res.currency', compute='_compute_try_currency_id')

    @api.depends_context('company')
    def _compute_try_currency_id(self):
        try_currency = self.env['res.currency'].search([('name', '=', 'TRY')], limit=1)
        for record in self:
            record.try_currency_id = try_currency

    @api.depends('partner_id', 'company_id')
    def _compute_balance_try(self):
        if not self:
            return
        lines = self.env['account.move.line.report'].search([
            ('partner_id', 'in', self.mapped('partner_id').ids),
            ('company_id', '=', self.env.company.id),
            ('line_type', '=', 'summary'),
        ])
        by_partner = defaultdict(float)
        for line in lines:
            by_partner[line.partner_id.id] += line.amount_tr_currency
        for record in self:
            record.balance_try = by_partner.get(record.partner_id.id, 0.0)

    def action_open_partner_statement(self):
        self.ensure_one()
        return self.partner_id.action_view_move_line_report()

    # To open partner statement from the ledger balance view, we need to override the get_formview_action method to call the action_open_partner_statement method.
    def get_formview_action(self, access_uid=None):
        self.ensure_one()
        return self.action_open_partner_statement()

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE VIEW account_ledger_balance AS (
                WITH latest_sale AS (
                    SELECT DISTINCT ON (partner_id, company_id)
                        partner_id,
                        company_id,
                        user_id
                    FROM sale_order
                    ORDER BY partner_id, company_id, date_order DESC NULLS LAST, id DESC
                )
                SELECT
                    ROW_NUMBER() OVER (ORDER BY alr.company_id, alr.partner_id) AS id,
                    alr.partner_id,
                    alr.company_id,
                    ls.user_id,
                    SUM(alr.balance) AS balance
                FROM account_move_line_report alr
                LEFT JOIN latest_sale ls
                    ON ls.partner_id = alr.partner_id
                   AND ls.company_id = alr.company_id
                WHERE alr.line_type = 'summary'
                GROUP BY alr.partner_id, alr.company_id, ls.user_id
            )
        """)
