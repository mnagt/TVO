from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    partner_balance = fields.Monetary(
        string='Balance',
        compute='_compute_partner_balance',
        currency_field='currency_id',
    )

    def _compute_partner_balance(self):
        if not self.ids:
            for partner in self:
                partner.partner_balance = 0.0
            return
        self.env.cr.execute("""
            SELECT partner_id, SUM(balance)
            FROM account_move_line_report
            WHERE partner_id IN %s AND line_type = 'summary'
            GROUP BY partner_id
        """, (tuple(self.ids),))
        balance_map = dict(self.env.cr.fetchall())
        for partner in self:
            partner.partner_balance = balance_map.get(partner.id, 0.0)

    def action_view_move_line_report(self):
        """Open Account Move Line Report for this partner"""
        self.ensure_one()
        action_name = _("Statement of Account")

        return {
            'type': 'ir.actions.act_window',
            'name': action_name,
            'res_model': 'account.move.line.report',
            'view_mode': 'list',
            'view_id': self.env.ref("partner_balance.view_account_move_line_report_tree").id,
            'domain': [('partner_id.id', '=', self.id), ('line_type', '=', 'summary')],
            'context': {
                'default_partner_id': self.id,
                'search_default_group_by_account': 1,
                'partner_name': self.name,
                'action_name': action_name,
            },
            'target': 'current',
        }
    