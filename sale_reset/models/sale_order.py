# -*- coding: utf-8 -*-

from odoo import models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
import logging
import time

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_convert_to_quotation(self):
        """
        Convert Sale Order to Quotation with binary logic following the flowchart:
        1. Check all related POs - any goods received?
        2. Check Sale Order - any deliveries made?
        3. Binary outcome: COMPLETE FAILURE or FULL SUCCESS
        """
        self.ensure_one()
        
        if self.state not in ['sale', 'done']:
            raise UserError("Only confirmed sales orders can be converted to quotations.")
        
        # Get all related purchase orders
        purchase_orders = self._get_related_purchase_orders()
        
        # STEP 1: Check All Related POs - Any goods received?
        po_goods_received = self._check_po_goods_received(purchase_orders)
        
        # STEP 2: Check Sale Order - Any deliveries made?
        so_deliveries_made = self._check_so_deliveries_made()
        
        # BINARY LOGIC: Any goods received OR deliveries made = COMPLETE FAILURE
        if po_goods_received or so_deliveries_made:
            # COMPLETE FAILURE PATH
            self._handle_complete_failure()
            
            # Show error notification only - don't reload for failures
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Cannot Convert',
                    'message': 'Cannot convert - order has received/delivered items',
                    'type': 'danger',
                    'sticky': True,
                }
            }
        
        # FULL SUCCESS PATH
        try:
            # Step 1: Cancel all related purchase orders
            self._cancel_purchase_orders(purchase_orders)
            
            # Step 2: Delete cancelled purchase orders
            self._delete_purchase_orders(purchase_orders)
            
            # Step 3: Cancel Sale Order and return to quotation
            self._convert_to_quotation_state()
            
            _logger.info(f"Successfully converted Sale Order {self.name} to quotation")
            
            # Simple form reload
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'current',
            }
            
        except Exception as e:
            # Complete failure - rollback any changes
            self.env.cr.rollback()
            _logger.error(f"Failed to convert Sale Order {self.name} to quotation: {str(e)}")
            raise UserError(f"Conversion failed: {str(e)}")

    def _get_related_purchase_orders(self):
        """Get all purchase orders related to this sale order"""
        purchase_orders = self.env['purchase.order'].sudo()

        # Get POs from sale order lines (use sudo to bypass access rights)
        for line in self.order_line:
            if line.product_id:
                # Find POs that might be related to this sale order line
                related_pos = self.env['purchase.order.line'].sudo().search([
                    ('product_id', '=', line.product_id.id),
                    ('order_id.origin', '=', self.name),
                    ('order_id.state', 'in', ['draft', 'sent', 'to approve', 'purchase'])
                ]).mapped('order_id')
                purchase_orders |= related_pos
        
        # Filter out any records that might have been deleted
        existing_pos = self.env['purchase.order'].sudo()
        for po in purchase_orders:
            try:
                # Test if record still exists by accessing a basic field
                po_exists = po.exists()
                if po_exists:
                    existing_pos |= po_exists
            except Exception as e:
                _logger.warning(f"Purchase Order {po.id} no longer exists: {str(e)}")
                continue
        
        return existing_pos

    def _check_po_goods_received(self, purchase_orders):
        """Check all related POs - any goods received?"""
        for po in purchase_orders:
            try:
                # Verify PO still exists before checking pickings
                if not po.exists():
                    _logger.warning(f"Purchase Order {po.id} no longer exists, skipping")
                    continue
                    
                for picking in po.picking_ids:
                    try:
                        if picking.exists() and picking.state == 'done':
                            return True
                    except Exception as e:
                        _logger.warning(f"Error checking picking {picking.id}: {str(e)}")
                        continue
            except Exception as e:
                _logger.warning(f"Error checking PO {po.id}: {str(e)}")
                continue
        return False
    
    def _check_so_deliveries_made(self):
        """Check Sale Order - any deliveries made?"""
        for picking in self.picking_ids:
            if picking.state == 'done':
                return True
        return False
    
    def _handle_complete_failure(self):
        """Handle complete failure - log attempt only, no changes made"""
        _logger.warning(f"Conversion attempt failed for Sale Order {self.name} - goods received/delivered")

    def _cancel_purchase_orders(self, purchase_orders):
        """Cancel all related purchase orders"""
        for po in purchase_orders:
            try:
                # Verify PO still exists before trying to cancel
                if not po.exists():
                    _logger.warning(f"Purchase Order {po.id} no longer exists, skipping cancellation")
                    continue
                
                # Refresh the record to get latest state
                po = po.with_context(active_test=False).browse(po.id)
                if not po.exists():
                    _logger.warning(f"Purchase Order {po.id} was deleted during process")
                    continue
                
                current_state = po.state
                if current_state in ['draft', 'sent', 'to approve']:
                    po.button_cancel()
                elif current_state == 'purchase':
                    po.button_cancel()
                elif current_state == 'cancel':
                    _logger.info(f"Purchase Order {po.name} already cancelled")
                else:
                    _logger.warning(f"Cannot cancel Purchase Order {po.name} in state {current_state}")
                    
            except Exception as e:
                _logger.error(f"Error cancelling Purchase Order {po.id}: {str(e)}")
                # Continue with other POs instead of failing completely
                continue

    def _delete_purchase_orders(self, purchase_orders):
        """Delete cancelled purchase orders"""
        for po in purchase_orders:
            try:
                # Verify PO still exists before trying to delete
                if not po.exists():
                    _logger.warning(f"Purchase Order {po.id} no longer exists, skipping deletion")
                    continue
                
                # Refresh the record to get latest state
                po = po.with_context(active_test=False).browse(po.id)
                if not po.exists():
                    _logger.warning(f"Purchase Order {po.id} was already deleted")
                    continue
                
                if po.state != 'cancel':
                    _logger.warning(f"Cannot delete Purchase Order {po.name} - not in cancelled state (current: {po.state})")
                    continue
                
                # Delete related records first (if they exist)
                try:
                    if po.order_line.exists():
                        po.order_line.unlink()
                except Exception as e:
                    _logger.warning(f"Error deleting PO lines for {po.name}: {str(e)}")
                
                # Delete the PO
                po_name = po.name  # Store name before deletion for logging
                po.unlink()
                _logger.info(f"Successfully deleted Purchase Order {po_name}")
                
            except Exception as e:
                _logger.error(f"Error deleting Purchase Order {po.id}: {str(e)}")
                # Continue with other POs instead of failing completely
                continue

    def _convert_to_quotation_state(self):
        """Convert sale order back to quotation state"""
        # Cancel delivery orders if any
        for picking in self.picking_ids:
            if picking.state not in ['done', 'cancel']:
                picking.action_cancel()
        
        # Store original state before changing
        original_state = self.state
        
        # Reset sale order to draft/quotation state
        self.action_unlock()
        self.write({
            'state': 'draft',
            'procurement_group_id': False,
        })
        
        # Reset sale order lines - only update fields that exist on sale.order.line
        for line in self.order_line:
            # Only update fields that actually exist on sale.order.line
            update_vals = {}
            # Most sale order line fields are automatically handled when the SO state changes
            # We don't need to manually update procurement_group_id on lines
            if update_vals:  # Only write if there are actual fields to update
                line.write(update_vals)
        
        # Trigger the same automated actions by simulating a cancel->draft transition
        self._trigger_conversion_email_via_automated_actions(original_state)

    def _trigger_conversion_email_via_automated_actions(self, original_state):
        """
        Trigger existing automated actions by simulating state transition
        This leverages your existing "Afkar Orders Canceled - Email" automated actions
        """
        try:
            _logger.info(f"Triggering automated actions for conversion of order {self.name}")
            
            # Temporarily change to 'cancel' state to trigger your automated actions
            self.with_context(skip_conversion_email=True).write({'state': 'cancel'})
            
            # Force commit to ensure the state change is persisted for automated actions
            self.env.cr.commit()
            
            # Small delay to ensure automated actions process
            time.sleep(0.1)
            
            # Change back to 'draft' state
            self.with_context(skip_conversion_email=True).write({'state': 'draft'})
            
            _logger.info(f"Successfully triggered automated actions for order {self.name}")
            
        except Exception as e:
            _logger.error(f"Error triggering automated actions for order {self.name}: {str(e)}")
            # Try fallback method
            self._send_conversion_canceled_email_fallback()

    def _send_conversion_canceled_email_fallback(self):
        """
        Fallback method: Direct email sending with simplified logic
        Only used if the automated action approach fails
        """
        try:
            # Find automated actions that match cancellation criteria
            automated_actions = self.env['ir.actions.server'].search([
                ('model_id.model', '=', 'sale.order'),
                ('state', '=', 'email'),
                ('name', 'ilike', 'cancel'),
                ('active', '=', True)
            ])
            
            _logger.info(f"Found {len(automated_actions)} automated actions for cancellation emails")
            
            for action in automated_actions:
                try:
                    # Check if this order matches the action's domain filter
                    if self._matches_automated_action_domain(action):
                        # Execute the email action directly
                        action.sudo().run()
                        _logger.info(f"Executed automated action: {action.name}")
                    else:
                        _logger.info(f"Order doesn't match domain for action: {action.name}")
                        
                except Exception as action_error:
                    _logger.error(f"Error executing automated action {action.name}: {str(action_error)}")
                    
        except Exception as e:
            _logger.error(f"Error in fallback email sending: {str(e)}")

    def _matches_automated_action_domain(self, action):
        """Check if current order matches the automated action's domain"""
        try:
            if not action.filter_domain:
                return True
            
            # Safely evaluate the domain using safe_eval for security
            domain = safe_eval(action.filter_domain) if action.filter_domain != 'Match all records' else []
            matching_records = self.search([('id', '=', self.id)] + domain)
            return bool(matching_records)
            
        except Exception as e:
            _logger.error(f"Error evaluating domain for action {action.name}: {str(e)}")
            return False
