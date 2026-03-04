from odoo import api, fields, models

CURRENCY_TRY = "TRY"


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    tr_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="TRY Currency",
        compute="_compute_tr_currency_id",
    )

    amount_tr_currency = fields.Monetary(
        string="TRY Value",
        compute="_compute_amount_tr_currency",
        store=True,
        currency_field="tr_currency_id",
    )

    tr_rate_display = fields.Char(
        string="TRY Rate",
        compute="_compute_amount_tr_currency",
        store=True,
    )

    def _get_try_currency(self):
        """Return the TRY res.currency record (cached per-environment)."""
        if not hasattr(self.env, "_try_currency_cache"):
            self.env._try_currency_cache = self.env["res.currency"].search(
                [("name", "=", CURRENCY_TRY)], limit=1
            )
        return self.env._try_currency_cache

    def _compute_tr_currency_id(self):
        """Always return TRY currency for monetary field formatting."""
        try_currency = self._get_try_currency()
        for rec in self:
            rec.tr_currency_id = try_currency

    @api.depends("currency_id", "amount_currency", "date", "company_id")
    def _compute_amount_tr_currency(self):
        """Compute the TRY equivalent of amount_currency and the rate used."""
        try_currency = self._get_try_currency()
        has_tcmb = 'l10n_tr_tcmb_rate' in self.env['account.move']._fields

        for line in self:
            if not try_currency or not line.currency_id:
                line.amount_tr_currency = 0.0
                line.tr_rate_display = ""
                continue

            if line.currency_id.name == CURRENCY_TRY:
                line.amount_tr_currency = line.amount_currency
                line.tr_rate_display = "1.0000"
                continue

            if line.currency_id == line.company_id.currency_id:
                line.amount_tr_currency = line.amount_currency
                line.tr_rate_display = "1.0000"
                continue

            tcmb_rate = 0.0
            if has_tcmb and line.move_id:
                tcmb_rate = line.move_id.l10n_tr_tcmb_rate or 0.0

            if tcmb_rate:
                line.amount_tr_currency = line.amount_currency * tcmb_rate
                line.tr_rate_display = f"{tcmb_rate:.4f}"
            else:
                rate_date = line.date or fields.Date.today()
                rate = self.env["res.currency"]._get_conversion_rate(
                    line.currency_id,
                    try_currency,
                    line.company_id or self.env.company,
                    rate_date,
                )
                line.amount_tr_currency = line.amount_currency * rate
                line.tr_rate_display = f"{rate:.4f}"