from odoo import api, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

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