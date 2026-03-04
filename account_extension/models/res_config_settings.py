from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    module_account_extension_sale_journal = fields.Boolean(
        string="Sale Order in Journal Items",
        help="Show Sales Order column and filter in Journal Items",
    )
    module_account_extension_try_journal = fields.Boolean(
        string="TRY Currency in Journal Items",
        help="Show TRY Value and TRY Rate columns in Journal Items",
    )
    module_account_extension_tl_gl = fields.Boolean(
        string="TL General Ledger",
        help="Enable the TL Equivalent General Ledger view under Accounting > Ledgers",
    )
    module_account_extension_discount_type = fields.Boolean(
        string="Discount Type on Invoice Lines",
        help="Enable percentage and fixed-amount discount types on invoice lines.",
    )