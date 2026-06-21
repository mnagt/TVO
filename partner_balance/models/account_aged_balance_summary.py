from odoo import api, models, fields, _
from odoo import tools


class AccountAgedBalanceSummary(models.Model):
    _name = 'account.aged.balance.summary'
    _description = 'Aged Balance Summary'
    _auto = False
    _order = 'partner_id'

    partner_id = fields.Many2one('res.partner', string='Partner', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    company_currency_id = fields.Many2one(
        'res.currency', string='Currency', related='company_id.currency_id', readonly=True
    )
    amount_current  = fields.Monetary(string='Current',   readonly=True, currency_field='company_currency_id')
    amount_1_30     = fields.Monetary(string='1-30',      readonly=True, currency_field='company_currency_id')
    amount_31_60    = fields.Monetary(string='31-60',     readonly=True, currency_field='company_currency_id')
    amount_61_90    = fields.Monetary(string='61-90',     readonly=True, currency_field='company_currency_id')
    amount_91_120   = fields.Monetary(string='91-120',    readonly=True, currency_field='company_currency_id')
    amount_older    = fields.Monetary(string='>120',      readonly=True, currency_field='company_currency_id')
    amount_total    = fields.Monetary(string='Total',     readonly=True, currency_field='company_currency_id')

    try_currency_id     = fields.Many2one('res.currency', compute='_compute_try_currency_id')
    amount_current_try  = fields.Monetary(string='Current', readonly=True, currency_field='try_currency_id')
    amount_1_30_try     = fields.Monetary(string='1-30',    readonly=True, currency_field='try_currency_id')
    amount_31_60_try    = fields.Monetary(string='31-60',   readonly=True, currency_field='try_currency_id')
    amount_61_90_try    = fields.Monetary(string='61-90',   readonly=True, currency_field='try_currency_id')
    amount_91_120_try   = fields.Monetary(string='91-120',  readonly=True, currency_field='try_currency_id')
    amount_older_try    = fields.Monetary(string='>120',    readonly=True, currency_field='try_currency_id')
    amount_total_try    = fields.Monetary(string='Total',   readonly=True, currency_field='try_currency_id')

    @api.depends_context('company')
    def _compute_try_currency_id(self):
        try_currency = self.env['res.currency'].search([('name', '=', 'TRY')], limit=1)
        for record in self:
            record.try_currency_id = try_currency

    def action_open_partner_aged_balance(self):
        self.ensure_one()
        view_id = self.env.ref('partner_balance.view_aged_balance_line_tree').id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Aged Balance'),
            'res_model': 'account.aged.balance.line',
            'view_mode': 'list',
            'view_id': view_id,
            'views': [(view_id, 'list')],
            'domain': [('partner_id', '=', self.partner_id.id), ('line_type', '=', 'summary')],
            'context': {
                'default_partner_id': self.partner_id.id,
                'search_default_group_by_bucket': 1,
                'report_type': 'aged',
                'partner_name': self.partner_id.name,
            },
            'target': 'current',
        }

    def get_formview_action(self, access_uid=None):
        self.ensure_one()
        return self.action_open_partner_aged_balance()

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE VIEW account_aged_balance_summary AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY company_id, partner_id) AS id,
                    partner_id,
                    company_id,
                    SUM(CASE WHEN bucket = 'current'  THEN amount_residual ELSE 0 END) AS amount_current,
                    SUM(CASE WHEN bucket = '1_30'     THEN amount_residual ELSE 0 END) AS amount_1_30,
                    SUM(CASE WHEN bucket = '31_60'    THEN amount_residual ELSE 0 END) AS amount_31_60,
                    SUM(CASE WHEN bucket = '61_90'    THEN amount_residual ELSE 0 END) AS amount_61_90,
                    SUM(CASE WHEN bucket = '91_120'   THEN amount_residual ELSE 0 END) AS amount_91_120,
                    SUM(CASE WHEN bucket = 'older'    THEN amount_residual ELSE 0 END) AS amount_older,
                    SUM(amount_residual) AS amount_total,
                    SUM(CASE WHEN bucket = 'current'  THEN amount_residual_try ELSE 0 END) AS amount_current_try,
                    SUM(CASE WHEN bucket = '1_30'     THEN amount_residual_try ELSE 0 END) AS amount_1_30_try,
                    SUM(CASE WHEN bucket = '31_60'    THEN amount_residual_try ELSE 0 END) AS amount_31_60_try,
                    SUM(CASE WHEN bucket = '61_90'    THEN amount_residual_try ELSE 0 END) AS amount_61_90_try,
                    SUM(CASE WHEN bucket = '91_120'   THEN amount_residual_try ELSE 0 END) AS amount_91_120_try,
                    SUM(CASE WHEN bucket = 'older'    THEN amount_residual_try ELSE 0 END) AS amount_older_try,
                    SUM(amount_residual_try) AS amount_total_try
                FROM account_aged_balance_line
                WHERE line_type = 'summary'
                GROUP BY partner_id, company_id
            )
        """)
