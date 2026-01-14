# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ChequeBulkStateUpdate(models.TransientModel):
    _name = 'cheque.bulk.state.update'
    _description = 'Bulk State Update for Cheques'

    line_ids = fields.One2many(
        'cheque.bulk.state.update.line',
        'wizard_id',
        string='Update Lines',
        required=True
    )

    @api.model
    def default_get(self, fields_list):
        """Pre-populate with selected cheques grouped by current state"""
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids', [])

        if active_ids and 'line_ids' in fields_list:
            # Get selected cheques
            cheques = self.env['account.cheque'].browse(active_ids)

            # State transition mapping
            STATE_TRANSITIONS = {
                'register': ['deposit', 'voided'],
                'deposit': ['bounce', 'cashed'],
                'bounce': ['deposit', 'voided'],
            }

            # Group cheques by current state
            lines = []
            cheques_by_state = {}
            for cheque in cheques:
                if cheque.state not in cheques_by_state:
                    cheques_by_state[cheque.state] = self.env['account.cheque']
                cheques_by_state[cheque.state] |= cheque

            # Create one line per state group (skip if no valid transitions)
            for state, state_cheques in cheques_by_state.items():
                # Skip states with no valid transitions (e.g., 'cashed')
                if state not in STATE_TRANSITIONS:
                    continue

                line_vals = {
                    'cheque_ids': [(6, 0, state_cheques.ids)],
                    'current_state': state,
                }

                # Auto-select state if only one option available
                allowed_codes = STATE_TRANSITIONS[state]
                if len(allowed_codes) == 1:
                    # Find the state option record
                    state_option = self.env['cheque.state.option'].search([('code', '=', allowed_codes[0])], limit=1)
                    if state_option:
                        line_vals['state_id'] = state_option.id

                lines.append((0, 0, line_vals))

            # If no lines created, raise error (all cheques in terminal states)
            if not lines:
                raise UserError(_('Selected cheques cannot be updated. They are already in a final state.'))

            res['line_ids'] = lines

        return res

    def _validate_all_operations(self):
        """Pre-validate all operations before processing - collect all errors at once"""
        self.ensure_one()
        errors = []

        # Basic validations
        if not self.line_ids:
            errors.append(_('Please add at least one update line.'))
            raise UserError('\n'.join(errors))

        # Validate no duplicate states
        state_ids = self.line_ids.filtered('state_id').mapped('state_id')
        if len(state_ids) != len(set(state_ids.ids)):
            errors.append(_('Each state can only be used once. Please remove duplicate states.'))

        # Validate no duplicate cheques
        all_cheques = self.env['account.cheque']
        for line in self.line_ids:
            if line.cheque_ids & all_cheques:
                duplicate_cheques = line.cheque_ids & all_cheques
                errors.append(
                    _('The following cheques are selected in multiple lines:\n%s') %
                    '\n'.join(['  - %s' % c.name for c in duplicate_cheques])
                )
            all_cheques |= line.cheque_ids

        # Validate each line
        for line in self.line_ids:
            if not line.cheque_ids:
                continue

            if not line.state:
                errors.append(_('Please select a target state for all lines.'))
                continue

            # Validate state transitions
            try:
                line._validate_state_transition()
            except UserError as e:
                errors.append(str(e))

            # Special validations for deposit action
            if line.state == 'deposit':
                # Required fields
                if not line.deposit_journal_id:
                    errors.append(_('Line "%s": Deposit Journal is required for Deposit action.') % line.state_id.name)
                if not line.deposit_date:
                    errors.append(_('Line "%s": Deposit Date is required for Deposit action.') % line.state_id.name)

                # Validate date not in future
                if line.deposit_date and line.deposit_date > fields.Date.today():
                    errors.append(_('Deposit date cannot be in the future.'))

            # Special validations for cashed action
            if line.state == 'cashed':
                # Required fields
                if not line.bank_account_id:
                    errors.append(_('Line "%s": Bank Account is required for Cashed action.') % line.state_id.name)
                if not line.cashed_date:
                    errors.append(_('Line "%s": Cashed Date is required for Cashed action.') % line.state_id.name)

                # Validate each cheque for cashed operation
                for cheque in line.cheque_ids:
                    # Check if already cashed
                    if cheque.state == 'cashed':
                        errors.append(_('Cheque %s is already in Done state and cannot be cashed again.') % cheque.name)

                    # Check if cashed_date already set
                    if cheque.cashed_date:
                        errors.append(_('Cheque %s has already been cashed on %s.') % (cheque.name, cheque.cashed_date))

                    # Validate payment exists
                    if not cheque.payment_id:
                        errors.append(_('Cheque %s has no associated payment.') % cheque.name)
                        continue

                    # Validate outstanding account
                    if not cheque.payment_id.outstanding_account_id:
                        errors.append(_('Cheque %s: Payment has no outstanding account configured.') % cheque.name)

                    # Validate journal
                    if not cheque.original_journal_id:
                        errors.append(_('Cheque %s has no original journal.') % cheque.name)

                    # Validate amount
                    if cheque.amount <= 0:
                        errors.append(_('Cheque %s has invalid amount: %s.') % (cheque.name, cheque.amount))

                # Validate bank account
                if line.bank_account_id:
                    if not line.bank_account_id.account_type:
                        errors.append(_('Selected bank account "%s" has no account type.') % line.bank_account_id.name)

                # Validate date not in future
                if line.cashed_date and line.cashed_date > fields.Date.today():
                    errors.append(_('Cashed date cannot be in the future.'))

        # Raise all errors together
        if errors:
            raise UserError(_('Validation Failed - Please fix the following issues:\n\n%s') % '\n\n'.join(errors))

    def action_confirm(self):
        """Execute state updates for all lines"""
        self.ensure_one()

        # Pre-validate everything before processing
        self._validate_all_operations()

        updated_cheques = self.env['account.cheque']

        for line in self.line_ids:
            if not line.cheque_ids:
                continue

            # Use appropriate action method based on state
            if line.state == 'cashed':
                # Cash each cheque using the model's action_cash method
                for cheque in line.cheque_ids:
                    cheque.action_cash(line.bank_account_id.id, line.cashed_date)
            elif line.state == 'voided':
                # Void/return creates journal entries to reverse outstanding line
                line.cheque_ids.action_void()
            elif line.state == 'deposit':
                # Deposit action - creates accounting move
                for cheque in line.cheque_ids:
                    cheque.action_deposit(
                        bank_journal_id=line.deposit_journal_id.id,
                        deposit_date=line.deposit_date
                    )
            elif line.state == 'bounce':
                # Bounce action
                for cheque in line.cheque_ids:
                    cheque.action_bounce()
            else:
                # Simple state update for other states
                line.cheque_ids.write({'state': line.state})

            updated_cheques |= line.cheque_ids

        # Send success notification
        message = _('%s cheque(s) updated successfully.') % len(updated_cheques)
        self.env['bus.bus']._sendone(
            self.env.user.partner_id,
            'simple_notification',
            {
                'type': 'success',
                'title': _('Success'),
                'message': message,
                'sticky': False,
            }
        )

        # Close wizard
        return {'type': 'ir.actions.act_window_close'}


class ChequeBulkStateUpdateLine(models.TransientModel):
    _name = 'cheque.bulk.state.update.line'
    _description = 'Bulk State Update Line'

    wizard_id = fields.Many2one(
        'cheque.bulk.state.update',
        required=True,
        ondelete='cascade'
    )

    current_state = fields.Char(
        string='Current State Code',
        help='The current state of cheques in this line'
    )

    current_state_display = fields.Char(
        string='From State',
        compute='_compute_current_state_display',
        store=True
    )

    state_id = fields.Many2one(
        'cheque.state.option',
        string='New State',
        required=True
    )

    state = fields.Char(
        related='state_id.code',
        string='State Code',
        readonly=True
    )

    available_state_ids = fields.Many2many(
        'cheque.state.option',
        relation='bulk_update_line_available_state_rel',
        column1='line_id',
        column2='state_id',
        compute='_compute_available_state_ids',
        string='Available States'
    )

    cheque_ids = fields.Many2many(
        'account.cheque',
        string='Cheques',
        required=True
    )

    # Fields for deposit action (when state = deposit)
    deposit_journal_id = fields.Many2one(
        'account.journal',
        string='Deposit Journal',
        domain="[('type', '=', 'bank')]",
        help='Bank journal where the cheque will be deposited'
    )

    deposit_date = fields.Date(
        string='Deposit Date',
        default=fields.Date.context_today,
        help='Date when the cheque is deposited'
    )

    # Fields for cashed action (when state = done)
    bank_account_id = fields.Many2one(
        'account.account',
        string='Bank Account',
        help='Bank account to cash the cheque to'
    )

    cashed_date = fields.Date(
        string='Cashed Date',
        default=fields.Date.context_today,
        help='Date when the cheque was cashed'
    )

    allowed_cheque_count = fields.Integer(
        compute='_compute_allowed_cheque_count',
        string='Available Cheques'
    )

    available_cheque_ids = fields.Many2many(
        'account.cheque',
        relation='bulk_update_line_available_cheque_rel',
        column1='line_id',
        column2='cheque_id',
        compute='_compute_available_cheque_ids',
        string='Available Cheques'
    )

    @api.depends('current_state')
    def _compute_current_state_display(self):
        """Display current state in title case"""
        for line in self:
            if line.current_state:
                line.current_state_display = line.current_state.replace('_', ' ').title()
            else:
                line.current_state_display = ''

    @api.depends('wizard_id.line_ids.state_id', 'current_state')
    def _compute_available_state_ids(self):
        """Compute available states based on current state transitions"""
        # State transition mapping based on button visibility
        STATE_TRANSITIONS = {
            'register': ['deposit', 'voided'],
            'deposit': ['bounce', 'cashed'],
            'bounce': ['deposit', 'voided'],
        }

        for line in self:
            # Get allowed state codes based on current state
            if line.current_state and line.current_state in STATE_TRANSITIONS:
                allowed_codes = STATE_TRANSITIONS[line.current_state]
                all_states = self.env['cheque.state.option'].search([('code', 'in', allowed_codes)])
            else:
                # No valid transitions for this state (e.g., 'cashed')
                all_states = self.env['cheque.state.option']

            if line.wizard_id:
                # Get states already used in other lines
                used_state_ids = line.wizard_id.line_ids.filtered(lambda l: l != line and l.state_id).mapped('state_id')
                line.available_state_ids = all_states - used_state_ids
            else:
                line.available_state_ids = all_states

    @api.depends('state', 'wizard_id.line_ids.cheque_ids', 'wizard_id.line_ids.state')
    def _compute_available_cheque_ids(self):
        """Compute available cheques based on state and excluding already selected ones"""
        for line in self:
            if not line.state:
                line.available_cheque_ids = self.env['account.cheque']
                continue

            domain = line._get_allowed_domain()
            line.available_cheque_ids = self.env['account.cheque'].search(domain)

    @api.depends('state', 'wizard_id.line_ids.cheque_ids')
    def _compute_allowed_cheque_count(self):
        """Count cheques that can transition to selected state"""
        for line in self:
            if not line.state:
                line.allowed_cheque_count = 0
                continue

            domain = line._get_allowed_domain()
            line.allowed_cheque_count = self.env['account.cheque'].search_count(domain)

    @api.onchange('state_id')
    def _onchange_state_id(self):
        """Return domain for cheque_ids based on selected state"""
        result = {}

        # Domain for cheque_ids
        if self.state:
            result['domain'] = {'cheque_ids': self._get_allowed_domain()}
        else:
            result['domain'] = {'cheque_ids': []}

        return result

    def _get_allowed_domain(self):
        """Get domain for allowed cheques based on target state"""
        self.ensure_one()

        # Base domain - only incoming cheques
        base_domain = [('payment_method_code', '=', 'cheque_incoming')]

        # State-specific domains based on button visibility conditions
        state_domains = {
            'deposit': [('state', 'in', ['register', 'bounce'])],
            'bounce': [('state', '=', 'deposit')],
            'voided': [('state', 'in', ['register', 'bounce'])],
        }

        if self.state in state_domains:
            domain = base_domain + state_domains[self.state]
        else:
            domain = base_domain

        # Exclude cheques already selected in other lines
        if self.wizard_id:
            other_lines = self.wizard_id.line_ids.filtered(lambda l: l != self)
            used_cheque_ids = other_lines.mapped('cheque_ids').ids
            if used_cheque_ids:
                domain.append(('id', 'not in', used_cheque_ids))

        return domain

    def _validate_state_transition(self):
        """Validate that all selected cheques can transition to target state"""
        self.ensure_one()

        if not self.cheque_ids:
            return

        # Check each cheque against allowed domain
        allowed_domain = self._get_allowed_domain()
        allowed_cheques = self.env['account.cheque'].search(allowed_domain)

        invalid_cheques = self.cheque_ids - allowed_cheques

        if invalid_cheques:
            raise UserError(
                _('The following cheques cannot be updated to state "%s":\n%s\n\n'
                  'Please remove them from this line or select a different state.') % (
                    self.state_id.name or '',
                    '\n'.join(['- %s (current state: %s)' % (c.name, c.state) for c in invalid_cheques])
                )
            )
