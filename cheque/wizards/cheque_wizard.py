# -*- coding: utf-8 -*-


from odoo import api, fields, models, _


                    
class ChequeWizard(models.TransientModel):
    _name = "cheque.wizard"
    
    cheque_date = fields.Date(string='Cheque Date')
    

    def cash_submit(self):  
        cheque_inc = self.env['cheque.manage'].search([])
        cheque_inc.cheque_date = self.cheque_date 
        return cheque_inc.write({'state': 'done'})
    
    
class ChequeTransferWizard(models.TransientModel):
    _name = "cheque.transfer.wizard"
    
    transfer_date = fields.Date(string='Transfered Date')
    contact = fields.Many2one('res.partner', 'Contact')
    

    def transfer_submit(self):  
        cheque_inc = self.env['cheque.manage'].search([])
        return cheque_inc.write({'state': 'transfer'})
    
                    
class ChequeOutgoingWizard(models.TransientModel):
    _name = "cheque.outgoing.wizard"
    
    cheque_date = fields.Date(string='Cheque Date')
    bank_acc = fields.Many2one('account.account', 'Bank Account')
    
    

    def cash_out_submit(self):
        """Cash the cheque using the model's action_cash method"""
        cheque_id = self.env[self._context.get('active_model')].browse(self._context.get('active_ids'))
        return cheque_id.action_cash(self.bank_acc.id, self.cheque_date)