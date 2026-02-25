# Part of Odoo. See LICENSE file for full copyright and licensing details.

CHEQUE_NEW_CODES = frozenset(['cheque_incoming', 'cheque_outgoing'])
CHEQUE_MOVE_CODES = frozenset(['cheque_existing_in', 'cheque_existing_out', 'cheque_return'])
CHEQUE_ALL_CODES = CHEQUE_NEW_CODES | CHEQUE_MOVE_CODES