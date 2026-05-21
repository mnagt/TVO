# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCurrencyRate(models.Model):
    _name = "res.currency.rate"
    _inherit = ["res.currency.rate", "mail.thread"]

    rate = fields.Float(tracking=True)
    forex_selling_rate = fields.Float(
        string="Forex Selling Rate",
        digits=(12, 6),
        tracking=True,
        help="TCMB Döviz Satış (Forex Selling) rate",
    )
    banknote_buying_rate = fields.Float(
        string="Banknote Buying Rate",
        digits=(12, 6),
        tracking=True,
        help="TCMB Efektif Alış (Banknote Buying) rate",
    )
    banknote_selling_rate = fields.Float(
        string="Banknote Selling Rate",
        digits=(12, 6),
        tracking=True,
        help="TCMB Efektif Satış (Banknote Selling) rate",
    )
    provider_id = fields.Many2one(
        string="Provider",
        comodel_name="res.currency.rate.provider",
        ondelete="restrict",
        tracking=True,
    )

    def write(self, values):
        """Unset link to provider in case rate fields or 'name' are manually changed"""
        rate_fields = {"rate", "forex_selling_rate", "banknote_buying_rate", "banknote_selling_rate", "name"}
        if any(f in values for f in rate_fields) and "provider_id" not in values:
            values["provider_id"] = False
        return super().write(values)
