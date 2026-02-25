from odoo import models, fields, api


class AccountJournal(models.Model):
    _inherit = "account.journal"

    cheque_collection_account_id = fields.Many2one(
        'account.account',
        string='Cheques Under Collection Account',
        domain="[('account_type', 'not in', ('asset_receivable', 'liability_payable')), ('company_ids', 'in', company_id)]",
        help='Account used when cheques are deposited but not yet cleared/cashed by the bank.',
    )

    @api.model
    def _get_reusable_payment_methods(self):
        """ We are able to have multiple times Checks payment method in a journal """
        res = super()._get_reusable_payment_methods()
        res.add("cheque_outgoing")
        return res
