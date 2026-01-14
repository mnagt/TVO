from odoo import fields, models, api, Command, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_date


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    new_cheque_ids = fields.One2many('account.cheque', 'payment_id', string='Checks')
    move_cheque_ids = fields.Many2many(
        comodel_name='account.cheque',
        relation='cheque_account_payment_rel',
        column1="payment_id",
        column2="check_id",
        required=True,
        copy=False,
        string="Checks Operations"
    )
    # Warning message in case of unlogical third party check operations
    cheque_warning_msg = fields.Text(compute='_compute_cheque_warning_msg')
    amount = fields.Monetary(compute="_compute_amount", readonly=False, store=True)

    @api.constrains('state', 'move_id')
    def _check_move_id(self):
        for payment in self:
            if (
                not payment.move_id and
                payment.payment_method_code in ('cheque_outgoing', 'cheque_incoming', 'cheque_existing_in', 'cheque_existing_out', 'cheque_return') and
                not payment.outstanding_account_id
            ):
                raise ValidationError(_("A payment with any Third Party Check or Own Check payment methods needs an outstanding account"))

    @api.depends('move_cheque_ids.amount', 'new_cheque_ids.amount', 'payment_method_code')
    def _compute_amount(self):
        for rec in self:
            checks = rec.new_cheque_ids if rec._is_cheque_payment(check_subtype='new_check') else rec.move_cheque_ids
            if checks:
                rec.amount = sum(checks.mapped('amount'))

    def _is_cheque_payment(self, check_subtype=False):
        if check_subtype == 'move_check':
            codes = ['cheque_existing_in', 'cheque_existing_out', 'cheque_return']
        elif check_subtype == 'new_check':
            codes = ['cheque_incoming', 'cheque_outgoing']
        else:
            codes = ['cheque_existing_in', 'cheque_existing_out', 'cheque_return', 'cheque_incoming', 'cheque_outgoing']
        return self.payment_method_code in codes

    def action_post(self):
        # unlink checks if payment method code is not for checks. We do it on post and not when changing payment
        # method so that the user don't loose checks data in case of changing payment method and coming back again
        # also, changing partner recompute payment method so all checks would be cleaned
        for payment in self.filtered(lambda x: x.new_cheque_ids and not x._is_cheque_payment(check_subtype='new_check')):
            payment.new_cheque_ids.unlink()
        if not self.env.context.get('l10n_ar_skip_remove_check'):
            for payment in self.filtered(lambda x: x.move_cheque_ids and not x._is_cheque_payment(check_subtype='move_check')):
                payment.move_cheque_ids = False
        msgs = self._get_blocking_warning_msg()
        if msgs:
            raise ValidationError('* %s' % '\n* '.join(msgs))
        super().action_post()
        # Set register status and link cheques to their move lines
        for payment in self:
            cheques = payment._get_cheques()
            if not cheques:
                continue

            # Find the outstanding/liquidity lines that correspond to each cheque
            liquidity_lines = payment._seek_for_lines()

            if len(cheques) == len(liquidity_lines):
                # Link each cheque to its corresponding line
                for check, line in zip(cheques, liquidity_lines):
                    check.outstanding_line_id = line.id
            elif len(cheques) == 1 and liquidity_lines:
                # Single cheque case
                cheques.outstanding_line_id = liquidity_lines[0].id

        # Set register status for incoming checks only
        incoming_checks = self.new_cheque_ids.filtered(lambda x: x.payment_method_code == 'cheque_incoming')
        if incoming_checks:
            incoming_checks.write({'state': 'register'})

    def _get_cheques(self):
        self.ensure_one()
        if self._is_cheque_payment(check_subtype='new_check'):
            return self.new_cheque_ids
        elif self._is_cheque_payment(check_subtype='move_check'):
            return self.move_cheque_ids
        else:
            return self.env['account.cheque']

    def _get_blocking_warning_msg(self):
        msgs = []
        for rec in self.filtered(lambda x: x.state == 'draft' and x._is_cheque_payment()):
            if any(rec.currency_id != check.currency_id for check in rec._get_cheques()):
                msgs.append(_('The currency of the payment and the currency of the check must be the same.'))
            if not rec.currency_id.is_zero(sum(rec._get_cheques().mapped('amount')) - rec.amount):
                msgs.append(
                    _('The amount of the payment  does not match the amount of the selected check. '
                      'Please try to deselect and select the check again.')
                )
            # checks being moved
            if rec._is_cheque_payment(check_subtype='move_check'):
                if any(check.payment_id.state == 'draft' for check in rec.move_cheque_ids):
                    msgs.append(
                        _('Selected checks "%s" are not posted', rec.move_cheque_ids.filtered(lambda x: x.payment_id.state == 'draft').mapped('display_name'))
                    )
                elif rec.payment_type == 'outbound' and any(check.current_journal_id != rec.journal_id for check in rec.move_cheque_ids):
                    # check outbound payment and transfer or inbound transfer
                    msgs.append(_(
                        'Some checks are not anymore in journal, it seems it has been moved by another payment.')
                    )
                elif rec.payment_type == 'inbound' and not rec._is_cheque_transfer() and any(rec.move_cheque_ids.mapped('current_journal_id')):
                    msgs.append(
                        _("Some checks are already in hand and can't be received again. Checks: %s",
                          ', '.join(rec.move_cheque_ids.mapped('display_name')))
                    )

                for check in rec.move_cheque_ids:
                    date = rec.date or fields.Datetime.now()

                    last_operation = check._get_last_operation()
                    if last_operation and last_operation[0].date > date:
                        msgs.append(
                            _(
                              "It seems you're trying to move a check with a date (%(date)s) prior to last "
                              "operation done with the check (%(last_operation)s). This may be wrong, please "
                              "double check it. By continue, the last operation on "
                              "the check will remain being %(last_operation)s",
                              date=format_date(self.env, date), last_operation=last_operation.display_name
                            )
                        )
        return msgs

    def _get_reconciled_checks_error(self):
        checks_reconciled = self.new_cheque_ids.filtered(lambda x: x.state in ['cashed', 'voided'])
        if checks_reconciled:
            raise UserError(
                _("You can't cancel or re-open a payment with checks if some check has been cashed or voided. "
                  "Checks:\n%s", ('\n'.join(['* %s (%s)' % (x.name, x.state) for x in checks_reconciled])))
            )

    def action_cancel(self):
        self._get_reconciled_checks_error()
        super().action_cancel()


    def action_draft(self):
        self._get_reconciled_checks_error()
        for payment in self:
            # Clear outstanding line references for all cheques
            cheques = payment._get_cheques()
            if cheques:
                cheques.write({'outstanding_line_id': False})
            # Set state to draft only for new cheques (not existing/move cheques)
            if payment.new_cheque_ids:
                payment.new_cheque_ids.write({'state': 'draft'})
        super().action_draft()


    @api.depends(
        'payment_method_line_id', 'state', 'date', 'amount', 'currency_id', 'company_id',
        'move_cheque_ids.issuer_vat', 'move_cheque_ids.bank_id', 'move_cheque_ids.payment_id.date',
        'new_cheque_ids.amount', 'new_cheque_ids.name',
    )
    def _compute_cheque_warning_msg(self):
        """
        Compute warning message for checks
        We use cheque_number as de dependency because on the interface this is the field the user is using.
        Another approach could be to add an onchange on _inversecheque_number method
        """
        self.cheque_warning_msg = False
        for rec in self.filtered(lambda x: x._is_cheque_payment()):
            msgs = rec._get_blocking_warning_msg()
            # new third party check uniqueness warning (on own checks it's done by a sql constraint)
            if rec.payment_method_code == 'cheque_incoming':
                same_checks = self.env['account.cheque']
                for check in rec.new_cheque_ids.filtered(
                        lambda x: x.name and x.payment_method_line_id.code == 'cheque_incoming' and
                        x.bank_id and x.issuer_vat):
                    same_checks += same_checks.search([
                        ('company_id', '=', rec.company_id.id),
                        ('bank_id', '=', check.bank_id.id),
                        ('issuer_vat', '=', check.issuer_vat),
                        ('name', '=', check.name),
                        ('payment_id.state', 'not in', ['draft', 'canceled']),
                        ('id', '!=', check._origin.id)], limit=1)
                if same_checks:
                    msgs.append(
                        _("Other checks were found with same number, issuer and bank. Please double check you are not "
                          "encoding the same check more than once. List of other payments/checks: %s",
                          ", ".join(same_checks.mapped('display_name')))
                    )
            rec.cheque_warning_msg = msgs and '* %s' % '\n* '.join(msgs) or False

    @api.model
    def _get_trigger_fields_to_synchronize(self):
        res = super()._get_trigger_fields_to_synchronize()
        return res + ('new_cheque_ids',)

    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None):
        """ Add check name and operation on liquidity line. For multiple cheques, create separate lines. """
        res = super()._prepare_move_line_default_vals(write_off_line_vals=write_off_line_vals, force_balance=force_balance)

        # Handle cheque payments
        if self._is_cheque_payment():
            cheques = self._get_cheques()

            if not cheques:
                return res

            # Multiple cheques: create separate liquidity lines for each cheque in the same move
            if len(cheques) > 1:
                liquidity_line_vals = res[0]  # Get the original liquidity line template
                new_liquidity_lines = []

                # Calculate total and individual amounts
                checks_total = sum(cheques.mapped('amount'))

                # Calculate original balance from debit and credit
                original_balance = liquidity_line_vals.get('debit', 0.0) - liquidity_line_vals.get('credit', 0.0)
                liquidity_balance_total = 0.0

                for check in cheques:
                    # Copy the original liquidity line values
                    check_line_vals = liquidity_line_vals.copy()

                    # Calculate balance for this cheque
                    if check == cheques[-1]:
                        # Last cheque gets the remaining balance to avoid rounding issues
                        liquidity_balance = self.currency_id.round(original_balance - liquidity_balance_total)
                    else:
                        liquidity_balance = self.currency_id.round(original_balance * check.amount / checks_total)
                        liquidity_balance_total += liquidity_balance

                    # Determine amount_currency based on payment direction
                    amount_currency = check.amount if liquidity_line_vals['amount_currency'] > 0 else -check.amount

                    # Update the line values for this cheque
                    check_line_vals.update({
                        'name': _(
                            'Check %(check_number)s - %(suffix)s',
                            check_number=check.name,
                            suffix=''.join([item[1] for item in self._get_aml_default_display_name_list()])),
                        'date_maturity': check.payment_date,
                        'amount_currency': amount_currency,
                        'debit': max(0.0, liquidity_balance),
                        'credit': -min(liquidity_balance, 0.0),
                    })

                    new_liquidity_lines.append(check_line_vals)

                # Replace the single liquidity line with multiple cheque lines
                res = new_liquidity_lines + res[1:]

            # Single cheque: just update the existing liquidity line
            else:
                check = cheques[0]
                res[0].update({
                    'name': _(
                        'Check %(check_number)s - %(suffix)s',
                        check_number=check.name,
                        suffix=''.join([item[1] for item in self._get_aml_default_display_name_list()])),
                    'date_maturity': check.payment_date,
                })

        return res

    @api.depends('move_cheque_ids')
    def _compute_destination_account_id(self):
        # EXTENDS 'account'
        super()._compute_destination_account_id()
        for payment in self:
            if payment.move_cheque_ids and (not payment.partner_id or payment.partner_id == payment.company_id.partner_id):
                payment.destination_account_id = payment.company_id.transfer_account_id.id

    def _is_cheque_transfer(self):
        self.ensure_one()
        return not self.partner_id and self.destination_account_id == self.company_id.transfer_account_id
