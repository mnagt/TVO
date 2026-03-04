from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import date


class SoToPoWizard(models.TransientModel):
    _name = 'so.to.po.wizard'
    _description = 'Convert Sale Order to Purchase Order'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        required=True,
        readonly=True,
    )

    target_company_id = fields.Many2one(
        'res.company',
        string='Target Company',
        compute='_compute_target_company_id',
        store=False,
        readonly=True,
    )

    @api.depends('sale_order_id')
    def _compute_target_company_id(self):
        for wizard in self:
            wizard.target_company_id = wizard.sale_order_id.intercompany_company_id

    def action_confirm(self):
        """Create the intercompany purchase order"""
        self.ensure_one()
        
        if not self.target_company_id:
            raise UserError(_('No target company found for the customer of this sale order.'))
        
        if self.sale_order_id.intercompany_po_id:
            raise UserError(_('This sale order has already been converted to a purchase order.'))
        
        # Switch to target company context
        target_company_env = self.env['purchase.order'].with_company(self.target_company_id)
        
        # Get delivery date
        commitment_date = self.sale_order_id.commitment_date
        delivery_date = commitment_date.date() if commitment_date else date.today()
        
        # Create purchase order in target company
        purchase_order = target_company_env.create({
            'company_id': self.target_company_id.id,
            'partner_id': self.sale_order_id.company_id.partner_id.id,
            'origin': self.sale_order_id.name,
            'date_order': fields.Datetime.now(),
        })
        
        # Create purchase order lines
        for line in self.sale_order_id.order_line:
            if line.display_type:  # Skip section/note lines
                continue
                
            # Create purchase order line in target company context
            target_po_line_env = self.env['purchase.order.line'].with_company(self.target_company_id)
            target_po_line_env.create({
                'order_id': purchase_order.id,
                'product_id': line.product_id.id,
                'name': line.name,
                'product_qty': line.product_uom_qty,
                'product_uom': line.product_uom.id,
                'price_unit': line.price_unit,
                'date_planned': delivery_date,
            })
        
        # Link the purchase order to the sale order
        self.sale_order_id.intercompany_po_id = purchase_order.id
        
        # Return action to open the created purchase order
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': purchase_order.id,
            'view_mode': 'form',
            'view_id': self.env.ref('purchase.purchase_order_form').id,
            'target': 'current',
        }