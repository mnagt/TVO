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


class ResUsers(models.Model):
    _inherit = 'res.users'

    pb_show_ledger       = fields.Boolean(string='Ledger',        compute='_compute_pb_config', inverse='_inverse_pb_config')
    pb_show_aged         = fields.Boolean(string='Aged',          compute='_compute_pb_config', inverse='_inverse_pb_config')
    pb_show_excel        = fields.Boolean(string='Excel Export',  compute='_compute_pb_config', inverse='_inverse_pb_config')
    pb_show_tl           = fields.Boolean(string='TL',            compute='_compute_pb_config', inverse='_inverse_pb_config')
    pb_show_usd          = fields.Boolean(string='USD',           compute='_compute_pb_config', inverse='_inverse_pb_config')
    pb_show_products     = fields.Boolean(string='Products',      compute='_compute_pb_config', inverse='_inverse_pb_config')
    pb_show_skip_opening = fields.Boolean(string='Skip Opening',  compute='_compute_pb_config', inverse='_inverse_pb_config')

    def _compute_pb_config(self):
        Config = self.env['partner.balance.user.config']
        for user in self:
            config = Config.search([('user_id', '=', user.id)], limit=1)
            user.pb_show_ledger       = config.show_ledger       if config else False
            user.pb_show_aged         = config.show_aged         if config else False
            user.pb_show_excel        = config.show_excel        if config else False
            user.pb_show_tl           = config.show_tl           if config else False
            user.pb_show_usd          = config.show_usd          if config else False
            user.pb_show_products     = config.show_products     if config else False
            user.pb_show_skip_opening = config.show_skip_opening if config else False

    def _inverse_pb_config(self):
        Config = self.env['partner.balance.user.config']
        for user in self:
            config = Config.search([('user_id', '=', user.id)], limit=1)
            vals = {
                'show_ledger':       user.pb_show_ledger,
                'show_aged':         user.pb_show_aged,
                'show_excel':        user.pb_show_excel,
                'show_tl':           user.pb_show_tl,
                'show_usd':          user.pb_show_usd,
                'show_products':     user.pb_show_products,
                'show_skip_opening': user.pb_show_skip_opening,
            }
            if config:
                config.write(vals)
            else:
                Config.create({'user_id': user.id, **vals})