# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):

    _inherit = 'account.move.line'

    cheque_ids = fields.One2many('account.cheque', 'outstanding_line_id', string='Checks')

    def reconcile(self):
        result = super().reconcile()
        for line in self:
            cheques = line.cheque_ids.filtered(lambda c: c.state == 'deposit')
            if not cheques or not line.full_reconcile_id:
                continue
            counterpart = line.full_reconcile_id.reconciled_line_ids - line
            # Bank account line is in the same move as the counterpart (suspense line),
            # not directly in reconciled_line_ids.
            # Exclude EXCH moves and the collection account itself to avoid
            # picking the wrong line (e.g. an exchange-difference line).
            collection_account = line.account_id
            bank_line = counterpart.move_id.line_ids.filtered(
                lambda l: l.account_id != collection_account
                          and not (l.move_id.name or '').startswith('EXCH/')
                          and l.account_id.account_type == 'asset_cash'
            )[:1]
            _logger.info(
                "CHEQUE AUTO-CASH [reconcile hook] cheque=%s "
                "reconciled_line_ids=%s counterpart_accounts=%s bank_line=%s",
                cheques.mapped('name'),
                line.full_reconcile_id.reconciled_line_ids.ids,
                counterpart.mapped('account_id.name'),
                bank_line.id or 'none',
            )
            if bank_line:
                cheques.write({
                    'state': 'cashed',
                    'cashed_date': bank_line.date or fields.Date.today(),
                    'outstanding_line_id': bank_line.id,
                })
        return result
