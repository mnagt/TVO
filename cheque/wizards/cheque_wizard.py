# -*- coding: utf-8 -*-

from odoo import fields, models


class ChequeOutgoingWizard(models.TransientModel):
    _name = "cheque.outgoing.wizard"
    
    cheque_date = fields.Date(string='Cheque Date')
    bank_acc = fields.Many2one('account.account', 'Bank Account')
    
    

    def cash_out_submit(self):
        """Cash the cheque using the model's action_cash method"""
        cheque_id = self.env[self._context.get('active_model')].browse(self._context.get('active_ids'))
        return cheque_id.action_cash(self.bank_acc.id, self.cheque_date)