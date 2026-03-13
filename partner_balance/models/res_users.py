from odoo import fields, models

class ResUsers(models.Model):
    _inherit = 'res.users'

    pb_view              = fields.Boolean(string='View',          compute='_compute_pb_config', inverse='_inverse_pb_config')
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
            user.pb_view              = config.show_view         if config else False
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
                'show_view':         user.pb_view,
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

