from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    module_sale_extension_sale_note = fields.Boolean(
        string="Sale Note with Bank Accounts",
        help="Auto-generate sale order notes with exchange rates and bank account selection.",
    )
    module_sale_extension_so_to_po = fields.Boolean(
        string="Intercompany SO to PO",
        help="Convert confirmed sale orders to purchase orders for intercompany transactions.",
    )