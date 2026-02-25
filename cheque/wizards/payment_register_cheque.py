# pylint: disable=protected-access
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
from ..models.mixins import ChequeIssuerMixin


class ChequePaymentRegisterCheck(ChequeIssuerMixin, models.TransientModel):
    _name = 'payment.register.cheque'
    _description = 'Payment register check'
    _check_company_auto = True

    payment_register_id = fields.Many2one('account.payment.register', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='payment_register_id.company_id')
    currency_id = fields.Many2one(related='payment_register_id.currency_id')
    name = fields.Char(string='Number')
    issuer_name = fields.Char(
        string='Issuer Name',
        compute='_compute_issuer_name', store=True, readonly=False,
    )
    bank_id = fields.Many2one(
        comodel_name='res.bank',
        compute='_compute_bank_id', store=True, readonly=False,
    )
    issuer_vat = fields.Char(
        string='Issuer VAT',
        compute='_compute_issuer_vat', store=True, readonly=False,
    )
    payment_date = fields.Date(readonly=False, required=True)
    amount = fields.Monetary()

    def _get_issuer_method_code(self):
        return self.payment_register_id.payment_method_line_id.code

    def _get_issuer_partner(self):
        return self.payment_register_id.partner_id

    @api.depends('payment_register_id.payment_method_line_id.code', 'payment_register_id.partner_id')
    def _compute_issuer_name(self):
        self._compute_issuer_fields()

    @api.depends('payment_register_id.payment_method_line_id.code', 'payment_register_id.partner_id')
    def _compute_bank_id(self):
        self._compute_issuer_fields()

    @api.depends('payment_register_id.payment_method_line_id.code', 'payment_register_id.partner_id')
    def _compute_issuer_vat(self):
        self._compute_issuer_fields()
