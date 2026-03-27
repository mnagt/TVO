# -*- coding: utf-8 -*-

from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def button_draft(self):
        """Override to allow draft reset for invoices sent to Nilvera (skip l10n_tr_nilvera_einvoice check)"""
        # Check if the feature is enabled for this company
        if not self.company_id.l10n_tr_draft_after_sent:
            return super().button_draft()
        
        # Skip ONLY odoo.addons.l10n_tr_nilvera_einvoice (not _usd or _extended)
        mro = self.__class__.__mro__
        
        for i, cls in enumerate(mro):
            # Find the EXACT l10n_tr_nilvera_einvoice module (not _usd, not _extended)
            if cls.__module__ == 'odoo.addons.l10n_tr_nilvera_einvoice.models.account_move':
                # Look for button_draft in classes AFTER this one
                for next_cls in mro[i+1:]:
                    method = next_cls.__dict__.get('button_draft')
                    if method:
                        return method(self)
                break
        
        # Fallback to super() if we don't find it
        return super().button_draft()
