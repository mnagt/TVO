# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class AccountMoveLine(models.Model):

    _inherit = 'account.move.line'

    cheque_ids = fields.One2many('account.cheque', 'outstanding_line_id', string='Checks')

    def _reconcile_plan(self, reconciliation_plan):
        """Auto-advance deposited cheques to 'cashed' when their collection-account
        line becomes fully reconciled.

        Overridden here (instead of `reconcile()`) because Odoo core also finalizes
        reconciliation through this method directly for internal settlements (e.g.
        currency exchange-difference, cash-basis tax) that never call the public
        `reconcile()` API - those paths must trigger the same auto-cash logic.

        Any full reconciliation of the line counts (not just a match against a real
        bank/cash account): per confirmed real-world usage, reconciling a deposited
        cheque's collection line - whatever it's matched against - is how the
        accountant marks the cheque as cashed. Scope is intentionally limited to the
        deposit -> cashed transition; no other cheque state is touched here.
        """
        result = super()._reconcile_plan(reconciliation_plan)
        all_lines = self.env['account.move.line']
        for group in reconciliation_plan:
            all_lines |= group
        for line in all_lines:
            all_cheques = line.cheque_ids
            if not all_cheques:
                continue
            cheques = all_cheques.filtered(lambda c: c.state == 'deposit')
            if not cheques or not line.reconciled:
                continue
            # full_reconcile_id can stay empty even when the line is fully closed
            # (e.g. closed via separate partial reconciles) - matched_debit_ids /
            # matched_credit_ids is the reliable source of the counterpart lines.
            partials = line.matched_debit_ids | line.matched_credit_ids
            counterparts = (partials.mapped('debit_move_id') | partials.mapped('credit_move_id')) - line
            counterpart_dates = counterparts.mapped('date')
            cashed_date = max(counterpart_dates) if counterpart_dates else fields.Date.today()
            cheques.write({
                'state': 'cashed',
                'cashed_date': cashed_date,
            })
        return result
