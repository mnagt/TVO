# -*- coding: utf-8 -*-

from odoo import api, fields, models


class PartnerBalanceUserConfig(models.Model):
    _name = 'partner.balance.user.config'
    _description = 'Partner Balance Button Visibility per User'
    _rec_name = 'user_id'

    user_id = fields.Many2one('res.users', required=True, ondelete='cascade', index=True)
    show_ledger = fields.Boolean(default=False)
    show_aged = fields.Boolean(default=False)
    show_excel = fields.Boolean(default=False)
    show_tl = fields.Boolean(default=False)
    show_usd = fields.Boolean(default=False)
    show_products = fields.Boolean(default=False)
    show_skip_opening = fields.Boolean(default=False)

    _sql_constraints = [
        ('user_uniq', 'UNIQUE(user_id)', 'One config per user.')
    ]

    # ── auto-manage group membership ────────────────────────────────────────
    def _has_any_access(self):
        """True if at least one show_* flag is enabled."""
        flags = ['show_ledger', 'show_aged', 'show_excel',
                 'show_tl', 'show_usd', 'show_products', 'show_skip_opening']
        return any(getattr(self, f) for f in flags)

    def _sync_group(self):
        group = self.env.ref('partner_balance.group_partner_balance_user')
        for rec in self:
            if rec._has_any_access():
                rec.user_id.groups_id = [(4, group.id)]
            else:
                rec.user_id.groups_id = [(3, group.id)]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_group()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._sync_group()
        return res

    def unlink(self):
        group = self.env.ref('partner_balance.group_partner_balance_user')
        for rec in self:
            rec.user_id.groups_id = [(3, group.id)]
        return super().unlink()

    # ── RPC method called from OWL ──────────────────────────────────────────
    @api.model
    def get_user_config(self):
        config = self.search([('user_id', '=', self.env.uid)], limit=1)
        defaults = dict(show_ledger=False, show_aged=False, show_excel=False,
                        show_tl=False, show_usd=False, show_products=False,
                        show_skip_opening=False)
        if not config:
            return defaults
        return {k: getattr(config, k) for k in defaults}