# Part of Odoo. See LICENSE file for full copyright and licensing details.
import stdnum
from odoo import api, fields


class ChequeIssuerMixin:
    """Mixin providing shared issuer-related computed fields and onchange logic
    for account.cheque and payment.register.cheque."""

    def _get_issuer_method_code(self):
        """Return the payment method code relevant to this record. Override in subclasses."""
        raise NotImplementedError

    def _get_issuer_partner(self):
        """Return the partner relevant to this record. Override in subclasses."""
        raise NotImplementedError

    @api.onchange('name')
    def _onchange_name(self):
        if self.name:
            self.name = self.name.zfill(8)

    @api.onchange('issuer_vat')
    def _clean_issuer_vat(self):
        for rec in self.filtered(lambda x: x.issuer_vat and x.company_id.country_id.code):
            stdnum_vat = stdnum.util.get_cc_module(rec.company_id.country_id.code, 'vat')
            if hasattr(stdnum_vat, 'compact'):
                rec.issuer_vat = stdnum_vat.compact(rec.issuer_vat)

    def _compute_issuer_fields(self):
        """Shared logic for _compute_issuer_name / _compute_bank_id / _compute_issuer_vat."""
        incoming = self.filtered(lambda x: x._get_issuer_method_code() == 'cheque_incoming')
        for rec in incoming:
            partner = rec._get_issuer_partner()
            rec.issuer_name = partner.name
            rec.bank_id = partner.bank_ids[:1].bank_id
            rec.issuer_vat = partner.vat
        (self - incoming).issuer_name = False
        (self - incoming).bank_id = False
        (self - incoming).issuer_vat = False