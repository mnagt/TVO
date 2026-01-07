from odoo import models, api


class AccountPaymentMethod(models.Model):
    _inherit = 'account.payment.method'

    @api.model
    def _get_payment_method_information(self):
        res = super()._get_payment_method_information()
        res['cheque_incoming'] = {'mode': 'multi', 'type': ('cash',)}
        res['cheque_existing_in'] = {'mode': 'multi', 'type': ('cash',)}
        res['cheque_existing_out'] = {'mode': 'multi', 'type': ('cash',)}
        res['cheque_return'] = {'mode': 'multi', 'type': ('bank',)}
        res['cheque_outgoing'] = {'mode': 'multi', 'type': ('bank',)}
        return res
