import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ChequeTransferWizard(models.TransientModel):
    _name = 'cheque.transfer.wizard'
    _description = 'Cheque Transfer Wizard'

    cheque_id = fields.Many2one(
        'account.cheque',
        string='Cheque',
        required=True,
    )
    deposit_journal_id = fields.Many2one(
        related='cheque_id.deposit_journal_id',
        string='Deposit Journal',
        readonly=True,
    )
    collection_account_id = fields.Many2one(
        'account.account',
        string='Collection Account',
        compute='_compute_collection_account_id',
        readonly=True,
    )
    transfer_account_id = fields.Many2one(
        'account.account',
        string='Transfer Account',
        required=True,
    )
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.today,
    )

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id:
            cheque = self.env['account.cheque'].browse(active_id)
            if cheque.state != 'deposit':
                raise UserError(_('Only deposited cheques can be transferred.'))
            res['cheque_id'] = cheque.id
        return res

    @api.depends('cheque_id')
    def _compute_collection_account_id(self):
        for wiz in self:
            wiz.collection_account_id = wiz.cheque_id.outstanding_line_id.account_id

    def action_confirm(self):
        self.ensure_one()
        cheque = self.cheque_id
        if cheque.outstanding_line_id.move_id.state != 'posted':
            raise UserError(_(
                'The deposit journal entry for cheque "%s" is not posted. '
                'Please re-post the deposit entry before transferring.'
            ) % cheque.name)
        credit_account = self.collection_account_id
        debit_account = self.transfer_account_id

        # --- DIAGNOSTIC LOG ---
        _logger.warning(
            "CHEQUE TRANSFER WIZARD\n"
            "  cheque.id=%s  cheque.state=%s\n"
            "  outstanding_line_id=%s  outstanding_line parent_state=%s\n"
            "  collection_account_id=%s\n"
            "  transfer_account_id=%s\n"
            "  deposit_journal_id=%s",
            cheque.id, cheque.state,
            cheque.outstanding_line_id.id,
            cheque.outstanding_line_id.parent_state,
            self.collection_account_id.id,
            self.transfer_account_id.id,
            cheque.deposit_journal_id.id,
        )
        # --- END DIAGNOSTIC LOG ---

        move = cheque._create_transition_move(
            debit_account=debit_account,
            credit_account=credit_account,
            journal_id=cheque.deposit_journal_id.id,
            date=self.date,
            label=_('Warranty: %s') % cheque.name,
            reconcile_line=cheque.outstanding_line_id,
        )
        transfer_line = move.line_ids.filtered(lambda l: l.account_id == debit_account)
        cheque.write({'state': 'warranty', 'outstanding_line_id': transfer_line.id})
        return {'type': 'ir.actions.act_window_close'}
