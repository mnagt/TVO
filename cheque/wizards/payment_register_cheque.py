# pylint: disable=protected-access
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import models, fields, api
import stdnum

_logger = logging.getLogger(__name__)


class ChequePaymentRegisterCheck(models.TransientModel):
    _name = 'payment.register.cheque'
    _description = 'Payment register check'
    _check_company_auto = True

    payment_register_id = fields.Many2one('account.payment.register', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='payment_register_id.company_id')
    currency_id = fields.Many2one(related='payment_register_id.currency_id')
    name = fields.Char(string='Number')
    issuer_partner_id = fields.Many2one(
        'res.partner',
        string='Cheque Issuer',
        help='Partner who owns this cheque (for third-party cheques). Leave empty for normal cheques.'
    )
    bank_id = fields.Many2one(
        comodel_name='res.bank',
        compute='_compute_bank_id', store=True, readonly=False,
    )
    issuer_vat = fields.Char(
        compute='_compute_issuer_vat', store=True, readonly=False,
    )
    payment_date = fields.Date(readonly=False, required=True)
    amount = fields.Monetary()

    @api.onchange('name')
    def _onchange_name(self):
        if self.name:
            self.name = self.name.zfill(8)

    @api.depends('payment_register_id.payment_method_line_id.code', 'payment_register_id.partner_id', 'issuer_partner_id')
    def _compute_bank_id(self):
        new_third_party_checks = self.filtered(lambda x: x.payment_register_id.payment_method_line_id.code == 'cheque_incoming')
        for rec in new_third_party_checks:
            # Use issuer partner if set, otherwise use payment partner
            partner = rec.issuer_partner_id if rec.issuer_partner_id else rec.payment_register_id.partner_id
            rec.bank_id = partner.bank_ids[:1].bank_id
        (self - new_third_party_checks).bank_id = False

    @api.depends('payment_register_id.payment_method_line_id.code', 'payment_register_id.partner_id', 'issuer_partner_id')
    def _compute_issuer_vat(self):
        new_third_party_checks = self.filtered(lambda x: x.payment_register_id.payment_method_line_id.code == 'cheque_incoming')
        for rec in new_third_party_checks:
            # Use issuer partner if set, otherwise use payment partner
            partner = rec.issuer_partner_id if rec.issuer_partner_id else rec.payment_register_id.partner_id
            rec.issuer_vat = partner.vat
        (self - new_third_party_checks).issuer_vat = False

    @api.onchange('issuer_vat')
    def _clean_issuer_vat(self):
        for rec in self.filtered(lambda x: x.issuer_vat and x.company_id.country_id.code):
            stdnum_vat = stdnum.util.get_cc_module(rec.company_id.country_id.code, 'vat')
            if hasattr(stdnum_vat, 'compact'):
                rec.issuer_vat = stdnum_vat.compact(rec.issuer_vat)
