from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    intercompany_company_id = fields.Many2one(
        'res.company',
        string='Intercompany Company',
        compute='_compute_intercompany_company_id',
        store=False,
        help='The company that this customer represents (if the customer is itself an Odoo company)'
    )

    intercompany_po_id = fields.Many2one(
        'purchase.order',
        string='Intercompany Purchase Order',
        check_company=False,
        help='The purchase order created from this sale order for intercompany transactions'
    )

    @api.depends('partner_id', 'partner_id.category_id')
    def _compute_intercompany_company_id(self):
        for order in self:
            intercom_tag = order.partner_id.category_id.filtered(
                lambda t: t.parent_id and t.parent_id.name == 'INTERCOM'
            )[:1]
            company = self.env['res.company']
            if intercom_tag:
                try:
                    company_id = int(intercom_tag.name)
                    company = self.env['res.company'].browse(company_id).exists()
                except ValueError:
                    pass
            order.intercompany_company_id = company or False

    def action_create_intercompany_po(self):
        """Open wizard to create intercompany purchase order"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'so.to.po.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('sale_extension_so_to_po.view_so_to_po_wizard_form').id,
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
            },
        }

    def action_view_intercompany_po(self):
        """Open the linked intercompany purchase order"""
        self.ensure_one()
        if not self.intercompany_po_id:
            return
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': self.intercompany_po_id.id,
            'view_mode': 'form',
            'view_id': self.env.ref('purchase.purchase_order_form').id,
            'target': 'current',
        }