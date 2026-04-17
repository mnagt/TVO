"""Combined post-migration: fixes outstanding_line_id and state on cheques.

Merges migrations 1.0.5 through 1.0.18 into a single file.
Each step runs in strict order — same result as running them separately.
"""
import logging

_logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Step 1 — originally 18.0.1.0.5
# ═══════════════════════════════════════════════════════════════════════════════
def _migrate_1_0_5(env):
    """Fix cheques reconciled via bank reconciliation that still show state='deposit'.

    For each deposited cheque whose outstanding_line_id is already fully reconciled
    against a bank/cash account line (asset_cash), update:
      - state → 'cashed'
      - cashed_date → date of the bank statement line
      - outstanding_line_id → the bank statement line
    """
    from odoo import fields

    cheques = env['account.cheque'].search([
        ('state', '=', 'deposit'),
        ('outstanding_line_id', '!=', False),
        ('outstanding_line_id.reconciled', '=', True),
    ])

    if not cheques:
        _logger.info("Migration 18.0.1.0.5: no affected cheques found.")
        return

    _logger.info(
        "Migration 18.0.1.0.5: found %d deposited cheque(s) with reconciled outstanding_line_id.",
        len(cheques),
    )

    fixed = 0
    skipped = 0
    for cheque in cheques:
        line = cheque.outstanding_line_id
        if not line.full_reconcile_id:
            _logger.warning(
                "Migration 18.0.1.0.5: cheque %s (ID=%s) — outstanding_line_id=%s is "
                "reconciled but has no full_reconcile_id. Skipping.",
                cheque.name, cheque.id, line.id,
            )
            skipped += 1
            continue

        counterpart = line.full_reconcile_id.reconciled_line_ids - line
        bank_line = counterpart.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_cash'
        )[:1]

        if not bank_line:
            _logger.warning(
                "Migration 18.0.1.0.5: cheque %s (ID=%s) — skipping. "
                "reconciled_line_ids=%s, counterpart lines: %s, counterpart move lines: %s",
                cheque.name, cheque.id,
                line.full_reconcile_id.reconciled_line_ids.ids,
                [(l.id, l.account_id.name, l.account_id.account_type) for l in counterpart],
                [(l.id, l.account_id.name, l.account_id.account_type)
                 for l in counterpart.move_id.line_ids],
            )
            skipped += 1
            continue

        cheque.write({
            'state': 'cashed',
            'cashed_date': bank_line.date or fields.Date.today(),
            'outstanding_line_id': bank_line.id,
        })
        _logger.info(
            "Migration 18.0.1.0.5: cheque %s (ID=%s) → state=cashed, "
            "cashed_date=%s, outstanding_line_id=%s (bank line in move %s).",
            cheque.name, cheque.id, bank_line.date, bank_line.id, bank_line.move_id.name,
        )
        fixed += 1

    _logger.info(
        "Migration 18.0.1.0.5 complete: %d cheque(s) updated to cashed, %d skipped.",
        fixed, skipped,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Step 2 — originally 18.0.1.0.6
# ═══════════════════════════════════════════════════════════════════════════════
def _migrate_1_0_6(env):
    """Fix stale outstanding_line_id from legacy deposits (pre-collection_line_id era).

    Follows the partial reconcile to find the correct collection line from the
    deposit JE and updates outstanding_line_id accordingly. If the collection line
    is also reconciled against a bank/cash account, the cheque is advanced to 'cashed'.
    """
    from odoo import fields

    cheques = env['account.cheque'].search([
        ('state', '=', 'deposit'),
        ('outstanding_line_id', '!=', False),
        ('outstanding_line_id.reconciled', '=', True),
    ])

    if not cheques:
        _logger.info("Migration 18.0.1.0.6: no affected cheques found.")
        return

    _logger.info(
        "Migration 18.0.1.0.6: found %d deposited cheque(s) with reconciled outstanding_line_id.",
        len(cheques),
    )

    fixed_deposit = 0
    fixed_cashed = 0
    skipped = 0

    for cheque in cheques:
        line = cheque.outstanding_line_id

        partial = (line.matched_debit_ids | line.matched_credit_ids)[:1]
        if not partial:
            _logger.warning(
                "Migration 18.0.1.0.6: cheque %s (ID=%s) — outstanding_line_id=%s "
                "is reconciled but has no partial reconcile entries. Skipping.",
                cheque.name, cheque.id, line.id,
            )
            skipped += 1
            continue

        direct_counterpart = (
            partial.credit_move_id if partial.debit_move_id == line else partial.debit_move_id
        )

        collection_line = direct_counterpart.move_id.line_ids.filtered(
            lambda l: l.account_id != line.account_id
        )[:1]

        if not collection_line:
            _logger.warning(
                "Migration 18.0.1.0.6: cheque %s (ID=%s) — could not find collection "
                "line in deposit JE (move %s). Lines: %s. Skipping.",
                cheque.name, cheque.id, direct_counterpart.move_id.name,
                [(l.id, l.account_id.name, l.account_id.account_type)
                 for l in direct_counterpart.move_id.line_ids],
            )
            skipped += 1
            continue

        if not collection_line.reconciled:
            cheque.write({'outstanding_line_id': collection_line.id})
            _logger.info(
                "Migration 18.0.1.0.6: cheque %s (ID=%s) → outstanding_line_id updated "
                "to %s (collection line, account=%s). State stays 'deposit'.",
                cheque.name, cheque.id, collection_line.id, collection_line.account_id.name,
            )
            fixed_deposit += 1
        else:
            if not collection_line.full_reconcile_id:
                _logger.warning(
                    "Migration 18.0.1.0.6: cheque %s (ID=%s) — collection line %s is "
                    "reconciled but has no full_reconcile_id. Skipping.",
                    cheque.name, cheque.id, collection_line.id,
                )
                skipped += 1
                continue

            coll_counterpart = collection_line.full_reconcile_id.reconciled_line_ids - collection_line
            bank_line = coll_counterpart.move_id.line_ids.filtered(
                lambda l: l.account_id.account_type == 'asset_cash'
            )[:1]

            if bank_line:
                cheque.write({
                    'state': 'cashed',
                    'cashed_date': bank_line.date or fields.Date.today(),
                    'outstanding_line_id': bank_line.id,
                })
                _logger.info(
                    "Migration 18.0.1.0.6: cheque %s (ID=%s) → state=cashed, "
                    "cashed_date=%s, outstanding_line_id=%s (bank line in move %s).",
                    cheque.name, cheque.id, bank_line.date, bank_line.id,
                    bank_line.move_id.name,
                )
                fixed_cashed += 1
            else:
                _logger.warning(
                    "Migration 18.0.1.0.6: cheque %s (ID=%s) — collection line %s is "
                    "reconciled but no asset_cash bank line found. "
                    "Collection counterpart lines: %s, move lines: %s. Skipping.",
                    cheque.name, cheque.id, collection_line.id,
                    [(l.id, l.account_id.name, l.account_id.account_type) for l in coll_counterpart],
                    [(l.id, l.account_id.name, l.account_id.account_type)
                     for l in coll_counterpart.move_id.line_ids],
                )
                skipped += 1

    _logger.info(
        "Migration 18.0.1.0.6 complete: %d fixed to deposit, %d advanced to cashed, %d skipped.",
        fixed_deposit, fixed_cashed, skipped,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Step 3 — originally 18.0.1.0.8
# ═══════════════════════════════════════════════════════════════════════════════
def _migrate_1_0_8(env):
    """Fix deposited cheques with NULL outstanding_line_id.

    Locates the deposit JE via deposit_journal_id + ref pattern and sets
    outstanding_line_id to the collection account line.
    """
    cheques = env['account.cheque'].search([
        ('state', '=', 'deposit'),
        ('outstanding_line_id', '=', False),
    ])

    if not cheques:
        _logger.info("Migration 18.0.1.0.8: no deposited cheques with NULL outstanding_line_id found.")
        return

    _logger.info(
        "Migration 18.0.1.0.8: found %d deposited cheque(s) with NULL outstanding_line_id.",
        len(cheques),
    )

    fixed = 0
    skipped = 0

    for cheque in cheques:
        collection_account = cheque.original_journal_id.cheque_collection_account_id
        if not collection_account:
            _logger.warning(
                "Migration 18.0.1.0.8: cheque %s (ID=%s) — original journal '%s' "
                "has no cheque_collection_account_id configured. Skipping.",
                cheque.name, cheque.id, cheque.original_journal_id.name,
            )
            skipped += 1
            continue

        if not cheque.deposit_journal_id:
            _logger.warning(
                "Migration 18.0.1.0.8: cheque %s (ID=%s) — no deposit_journal_id set. Skipping.",
                cheque.name, cheque.id,
            )
            skipped += 1
            continue

        deposit_move = env['account.move'].search([
            ('journal_id', '=', cheque.deposit_journal_id.id),
            ('state', '=', 'posted'),
            ('ref', 'ilike', 'Deposit: %s' % cheque.name),
        ], limit=1, order='date desc, id desc')

        if not deposit_move:
            _logger.warning(
                "Migration 18.0.1.0.8: cheque %s (ID=%s) — could not find deposit JE "
                "in journal '%s' with ref matching 'Deposit: %s'. Skipping.",
                cheque.name, cheque.id, cheque.deposit_journal_id.name, cheque.name,
            )
            skipped += 1
            continue

        collection_line = deposit_move.line_ids.filtered(
            lambda l: l.account_id == collection_account
        )[:1]

        if not collection_line:
            _logger.warning(
                "Migration 18.0.1.0.8: cheque %s (ID=%s) — deposit JE %s (ID=%s) has no "
                "line on collection account '%s'. Lines: %s. Skipping.",
                cheque.name, cheque.id,
                deposit_move.name, deposit_move.id,
                collection_account.display_name,
                [(l.id, l.account_id.display_name) for l in deposit_move.line_ids],
            )
            skipped += 1
            continue

        if collection_line.reconciled:
            _logger.warning(
                "Migration 18.0.1.0.8: cheque %s (ID=%s) — collection line %s is already "
                "reconciled. This cheque may need manual review. Setting outstanding_line_id anyway.",
                cheque.name, cheque.id, collection_line.id,
            )

        cheque.write({'outstanding_line_id': collection_line.id})
        _logger.info(
            "Migration 18.0.1.0.8: cheque %s (ID=%s) → outstanding_line_id set to %s "
            "(collection line in move %s, account=%s).",
            cheque.name, cheque.id, collection_line.id,
            deposit_move.name, collection_account.display_name,
        )
        fixed += 1

    _logger.info(
        "Migration 18.0.1.0.8 complete: %d fixed, %d skipped (of %d total).",
        fixed, skipped, len(cheques),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Step 4 — originally 18.0.1.0.9
# ═══════════════════════════════════════════════════════════════════════════════
def _migrate_1_0_9(env):
    """Fix cashed cheques whose outstanding_line_id points to EXCH entries.

    Locate the real deposit JE via journal + ref pattern, find the collection
    line, follow its full_reconcile_id to the real bank line (asset_cash), and
    update outstanding_line_id.
    """
    all_cashed = env['account.cheque'].search([
        ('state', '=', 'cashed'),
        ('outstanding_line_id', '!=', False),
    ])

    cheques = all_cashed.filtered(
        lambda c: c.outstanding_line_id.move_id.name
        and c.outstanding_line_id.move_id.name.startswith('EXCH/')
    )

    if not cheques:
        _logger.info("Migration 18.0.1.0.9: no cashed cheques with EXCH outstanding_line_id found.")
        return

    _logger.info(
        "Migration 18.0.1.0.9: found %d cashed cheque(s) with EXCH outstanding_line_id: %s",
        len(cheques), cheques.mapped('name'),
    )

    fixed = 0
    skipped = 0

    for cheque in cheques:
        collection_account = cheque.original_journal_id.cheque_collection_account_id
        if not collection_account:
            _logger.warning(
                "Migration 18.0.1.0.9: cheque %s (ID=%s) — original journal '%s' has no "
                "cheque_collection_account_id. Skipping.",
                cheque.name, cheque.id, cheque.original_journal_id.name,
            )
            skipped += 1
            continue

        if not cheque.deposit_journal_id:
            _logger.warning(
                "Migration 18.0.1.0.9: cheque %s (ID=%s) — no deposit_journal_id. Skipping.",
                cheque.name, cheque.id,
            )
            skipped += 1
            continue

        deposit_move = env['account.move'].search([
            ('journal_id', '=', cheque.deposit_journal_id.id),
            ('state', '=', 'posted'),
            ('ref', 'ilike', 'Deposit: %s' % cheque.name),
        ], limit=1, order='date desc, id desc')

        if not deposit_move:
            _logger.warning(
                "Migration 18.0.1.0.9: cheque %s (ID=%s) — could not find deposit JE "
                "in journal '%s' with ref 'Deposit: %s'. Skipping.",
                cheque.name, cheque.id, cheque.deposit_journal_id.name, cheque.name,
            )
            skipped += 1
            continue

        collection_line = deposit_move.line_ids.filtered(
            lambda l: l.account_id == collection_account
        )[:1]

        if not collection_line:
            _logger.warning(
                "Migration 18.0.1.0.9: cheque %s (ID=%s) — deposit JE %s has no line on "
                "collection account '%s'. Lines: %s. Skipping.",
                cheque.name, cheque.id, deposit_move.name,
                collection_account.display_name,
                [(l.id, l.account_id.display_name) for l in deposit_move.line_ids],
            )
            skipped += 1
            continue

        if not collection_line.full_reconcile_id:
            _logger.warning(
                "Migration 18.0.1.0.9: cheque %s (ID=%s) — collection line %s in move %s "
                "has no full_reconcile_id (not fully reconciled). Skipping.",
                cheque.name, cheque.id, collection_line.id, deposit_move.name,
            )
            skipped += 1
            continue

        counterparts = (
            collection_line.full_reconcile_id.reconciled_line_ids - collection_line
        ).filtered(
            lambda l: not (l.move_id.name or '').startswith('EXCH/')
        )

        if not counterparts:
            _logger.warning(
                "Migration 18.0.1.0.9: cheque %s (ID=%s) — no non-EXCH counterpart lines "
                "found in full_reconcile %s. All reconciled lines: %s. Skipping.",
                cheque.name, cheque.id,
                collection_line.full_reconcile_id.id,
                [(l.id, l.move_id.name, l.account_id.display_name)
                 for l in collection_line.full_reconcile_id.reconciled_line_ids],
            )
            skipped += 1
            continue

        bank_line = counterparts.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_cash'
        )[:1]

        if not bank_line:
            _logger.warning(
                "Migration 18.0.1.0.9: cheque %s (ID=%s) — no asset_cash line found in "
                "counterpart moves. Counterpart moves: %s. Skipping.",
                cheque.name, cheque.id,
                [(m.name, [(l.id, l.account_id.display_name, l.account_id.account_type)
                           for l in m.line_ids])
                 for m in counterparts.move_id],
            )
            skipped += 1
            continue

        old_line = cheque.outstanding_line_id
        cheque.write({'outstanding_line_id': bank_line.id})

        _logger.info(
            "Migration 18.0.1.0.9: cheque %s (ID=%s) → outstanding_line_id fixed: "
            "%s (EXCH move %s) → %s (bank line in move %s, account=%s).",
            cheque.name, cheque.id,
            old_line.id, old_line.move_id.name,
            bank_line.id, bank_line.move_id.name, bank_line.account_id.display_name,
        )
        fixed += 1

    _logger.info(
        "Migration 18.0.1.0.9 complete: %d fixed, %d skipped (of %d total).",
        fixed, skipped, len(cheques),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Step 5 — originally 18.0.1.0.10
# ═══════════════════════════════════════════════════════════════════════════════
def _migrate_1_0_10(env):
    """Fix broken cashed cheques with wrong outstanding_line_id.

    Cases:
      A) outstanding_line_id on 101011, reconciled=True  → fix pointer to bank line
      B) outstanding_line_id on 101011, reconciled=False → revert state to 'deposit'
           BUT first check if a bank statement line exists for this cheque
      C) outstanding_line_id on 101010                  → revert state to 'paid'/'deposit'
    """
    cashed = env['account.cheque'].search([
        ('state', '=', 'cashed'),
        ('outstanding_line_id', '!=', False),
    ])
    broken = cashed.filtered(
        lambda c: c.outstanding_line_id.account_id
                  != c.deposit_journal_id.default_account_id
    )
    _logger.info("Migration 18.0.1.0.10: found %d broken cashed cheques.", len(broken))

    fixed_pointer = reverted_deposit = reverted_paid = skipped = 0

    for c in broken:
        ol = c.outstanding_line_id
        coll_acc = c.original_journal_id.cheque_collection_account_id
        bank_acc = c.deposit_journal_id.default_account_id

        # ── Case B / Special: outstanding on 101011, NOT reconciled ─────────
        if ol.account_id == coll_acc and not ol.reconciled:
            stripped = c.name.lstrip('0') or '0'
            bsl = env['account.bank.statement.line'].search(
                [('payment_ref', 'ilike', stripped)], limit=1
            )
            if bsl and bsl.move_id and bank_acc:
                bank_line = bsl.move_id.line_ids.filtered(
                    lambda l: l.account_id == bank_acc
                )[:1]
                if bank_line:
                    c.write({'outstanding_line_id': bank_line.id})
                    _logger.info(
                        "18.0.1.0.10: cheque %s — BSL confirmed cashed. "
                        "Pointer fixed to line %s in %s.",
                        c.name, bank_line.id, bsl.move_id.name
                    )
                    fixed_pointer += 1
                    continue

            c.write({'state': 'deposit', 'cashed_date': False})
            _logger.info(
                "18.0.1.0.10: cheque %s — unreconciled collection line, "
                "no bank statement found. Reverted to 'deposit'.", c.name
            )
            reverted_deposit += 1
            continue

        # ── Case A: outstanding on 101011, reconciled=True ───────────────────
        if ol.account_id == coll_acc and ol.reconciled:
            if not ol.full_reconcile_id or not bank_acc:
                _logger.warning(
                    "18.0.1.0.10: cheque %s — reconciled but no full_reconcile or "
                    "no bank_acc. Skipping.", c.name
                )
                skipped += 1
                continue
            counterparts = ol.full_reconcile_id.reconciled_line_ids - ol
            non_exch = counterparts.filtered(
                lambda l: not (l.move_id.name or '').startswith('EXCH/')
            )
            bank_line = non_exch.move_id.line_ids.filtered(
                lambda l: l.account_id == bank_acc
            )[:1]
            if bank_line:
                c.write({'outstanding_line_id': bank_line.id})
                _logger.info(
                    "18.0.1.0.10: cheque %s — pointer fixed to line %s in %s.",
                    c.name, bank_line.id, bank_line.move_id.name
                )
                fixed_pointer += 1
            else:
                _logger.warning(
                    "18.0.1.0.10: cheque %s — reconciled but no bank line found "
                    "in non-EXCH counterparts. Skipping.", c.name
                )
                skipped += 1
            continue

        # ── Case C: outstanding on 101010 (EXCH chain) ──────────────────────
        if ol.account_id.code == '101010':
            target_state = 'deposit' if c.deposit_date else 'paid'
            new_ol = env['account.move.line']
            chain = env['account.move.line']
            if ol.full_reconcile_id:
                chain = ol.full_reconcile_id.reconciled_line_ids.filtered(
                    lambda l: l.account_id.code == '101010'
                )
                new_ol = chain.filtered(lambda l: not l.reconciled)[:1]
            if not new_ol and chain:
                exch_lines = chain.sorted(key=lambda l: (l.move_id.date, l.id), reverse=True)
                new_ol = exch_lines[:1]
            vals = {'state': target_state, 'cashed_date': False}
            if new_ol:
                vals['outstanding_line_id'] = new_ol.id
            c.write(vals)
            _logger.info(
                "18.0.1.0.10: cheque %s — reverted to '%s', "
                "outstanding_line_id → %s.",
                c.name, target_state, new_ol.id if new_ol else 'unchanged'
            )
            reverted_paid += 1
            continue

        _logger.warning(
            "18.0.1.0.10: cheque %s — unhandled case (account=%s, reconciled=%s). Skipping.",
            c.name, ol.account_id.code, ol.reconciled
        )
        skipped += 1

    _logger.info(
        "18.0.1.0.10 complete: %d pointer-fixed, %d reverted-to-deposit, "
        "%d reverted-to-paid, %d skipped.",
        fixed_pointer, reverted_deposit, reverted_paid, skipped
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Step 6 — originally 18.0.1.0.11
# ═══════════════════════════════════════════════════════════════════════════════
def _migrate_1_0_11(env):
    """Fix deposited cheques whose outstanding_line_id points to an EXCH move.

    Also picks up deposited cheques with NULL outstanding_line_id.
    Locates the real deposit JE, finds the collection line, and sets outstanding_line_id.
    """
    deposited = env['account.cheque'].search([
        ('state', '=', 'deposit'),
        ('outstanding_line_id', '!=', False),
    ])

    broken = deposited.filtered(
        lambda c: (c.outstanding_line_id.move_id.name or '').startswith('EXCH/')
    )

    null_outstanding = env['account.cheque'].search([
        ('state', '=', 'deposit'),
        ('outstanding_line_id', '=', False),
    ])

    _logger.info(
        "Migration 18.0.1.0.11: %d deposited cheque(s) with EXCH outstanding, "
        "%d with NULL outstanding.",
        len(broken), len(null_outstanding),
    )

    fixed = 0
    skipped = 0

    for c in broken | null_outstanding:
        coll_acc = c.original_journal_id.cheque_collection_account_id
        if not coll_acc:
            _logger.warning(
                "18.0.1.0.11: cheque %s — original journal '%s' has no "
                "cheque_collection_account_id. Skipping.",
                c.name, c.original_journal_id.name,
            )
            skipped += 1
            continue

        if not c.deposit_journal_id:
            _logger.warning(
                "18.0.1.0.11: cheque %s — no deposit_journal_id. Skipping.",
                c.name,
            )
            skipped += 1
            continue

        deposit_move = env['account.move'].search([
            ('journal_id', '=', c.deposit_journal_id.id),
            ('state', '=', 'posted'),
            ('ref', 'ilike', 'Deposit: %s' % c.name),
        ], limit=1, order='date desc, id desc')

        if not deposit_move:
            _logger.warning(
                "18.0.1.0.11: cheque %s — no posted deposit JE found in journal "
                "'%s' with ref matching 'Deposit: %s'. Skipping.",
                c.name, c.deposit_journal_id.name, c.name,
            )
            skipped += 1
            continue

        coll_line = deposit_move.line_ids.filtered(
            lambda l: l.account_id == coll_acc
        )[:1]

        if not coll_line:
            _logger.warning(
                "18.0.1.0.11: cheque %s — deposit JE %s has no line on "
                "collection account %s. Lines: %s. Skipping.",
                c.name, deposit_move.name, coll_acc.code,
                [(l.id, l.account_id.code) for l in deposit_move.line_ids],
            )
            skipped += 1
            continue

        if coll_line.reconciled:
            _logger.warning(
                "18.0.1.0.11: cheque %s — collection line %s in %s is already "
                "reconciled (full_rec=%s). Unexpected — skipping to avoid "
                "overwriting a valid reconciled state.",
                c.name, coll_line.id, deposit_move.name,
                coll_line.full_reconcile_id.id,
            )
            skipped += 1
            continue

        old_ol = c.outstanding_line_id
        c.write({'outstanding_line_id': coll_line.id})

        _logger.info(
            "18.0.1.0.11: cheque %s — outstanding_line_id: %s (%s) → %s (%s, %s).",
            c.name,
            old_ol.id if old_ol else None,
            old_ol.move_id.name if old_ol else None,
            coll_line.id,
            deposit_move.name,
            coll_acc.code,
        )
        fixed += 1

    _logger.info(
        "Migration 18.0.1.0.11 complete: %d fixed, %d skipped.",
        fixed, skipped,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Step 7 — originally 18.0.1.0.12
# ═══════════════════════════════════════════════════════════════════════════════
def _migrate_1_0_12(env):
    """Fix remaining deposited cheques that were cashed via bank reconciliation.

    Searches account.bank.statement.line by payment_ref matching the cheque
    number (without leading zeros). If a BSL confirms the cheque was cleared,
    updates state → 'cashed' with the bank line from the BSL move.
    """
    deposited = env['account.cheque'].search([('state', '=', 'deposit')])
    if not deposited:
        _logger.info("Migration 18.0.1.0.12: no deposited cheques found.")
        return

    _logger.info(
        "Migration 18.0.1.0.12: found %d deposited cheque(s). Checking for bank statement matches.",
        len(deposited),
    )

    fixed = skipped_no_bsl = skipped_no_bank_line = skipped_no_journal = 0

    for c in deposited:
        stripped = c.name.lstrip('0') or '0'

        if not c.deposit_journal_id:
            _logger.warning(
                "18.0.1.0.12: cheque %s (ID=%s) — no deposit_journal_id. Skipping.",
                c.name, c.id,
            )
            skipped_no_journal += 1
            continue

        bsl = env['account.bank.statement.line'].search(
            [('payment_ref', 'ilike', stripped)], limit=1,
        )
        if not bsl:
            _logger.info(
                "18.0.1.0.12: cheque %s (ID=%s) — no bank statement line found. Skipping.",
                c.name, c.id,
            )
            skipped_no_bsl += 1
            continue

        bank_acc = c.deposit_journal_id.default_account_id
        bank_line = bsl.move_id.line_ids.filtered(
            lambda l, acc=bank_acc: l.account_id == acc
        )[:1]

        if not bank_line:
            _logger.warning(
                "18.0.1.0.12: cheque %s (ID=%s) — BSL %s found but no line matching "
                "bank account %s in move %s. Skipping.",
                c.name, c.id, bsl.id, bank_acc.display_name, bsl.move_id.name,
            )
            skipped_no_bank_line += 1
            continue

        c.write({
            'state': 'cashed',
            'cashed_date': bank_line.date,
            'outstanding_line_id': bank_line.id,
        })
        _logger.info(
            "18.0.1.0.12: cheque %s (ID=%s) → state=cashed, cashed_date=%s, "
            "outstanding_line_id=%s (move %s).",
            c.name, c.id, bank_line.date, bank_line.id, bsl.move_id.name,
        )
        fixed += 1

    _logger.info(
        "Migration 18.0.1.0.12 complete: %d fixed, %d skipped (no BSL), "
        "%d skipped (no bank line), %d skipped (no journal).",
        fixed, skipped_no_bsl, skipped_no_bank_line, skipped_no_journal,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Step 8 — originally 18.0.1.0.13
# ═══════════════════════════════════════════════════════════════════════════════
def _migrate_1_0_13(env):
    """Fix outstanding_line_id on existing voided cheques.

    Two-path strategy:
    - Path A: outstanding_line_id exists and is reconciled → navigate via full_reconcile_id
    - Path B: outstanding_line_id is False or unreconciled → search void move by ref
    """
    voided = env['account.cheque'].search([('state', '=', 'voided')])
    if not voided:
        _logger.info("Migration 18.0.1.0.13: no voided cheques found.")
        return

    _logger.info(
        "Migration 18.0.1.0.13: found %d voided cheque(s). Checking outstanding_line_id.",
        len(voided),
    )

    fixed = skipped = 0

    for c in voided:
        old_line = c.outstanding_line_id

        if old_line and old_line.move_id.ref and 'Void cheque' in old_line.move_id.ref:
            _logger.info(
                "18.0.1.0.13: cheque %s (ID=%s) — already fixed. Skipping.",
                c.name, c.id,
            )
            skipped += 1
            continue

        # Path A: navigate via full_reconcile_id
        if old_line and old_line.full_reconcile_id:
            void_line_1 = old_line.full_reconcile_id.reconciled_line_ids - old_line
            if void_line_1:
                void_line_0 = void_line_1.move_id.line_ids - void_line_1
                if void_line_0:
                    c.outstanding_line_id = void_line_0
                    fixed += 1
                    _logger.info(
                        "18.0.1.0.13: cheque %s (ID=%s) — fixed via Path A (full_reconcile_id). "
                        "Move: %s → %s.",
                        c.name, c.id, old_line.move_id.name, void_line_0.move_id.name,
                    )
                    continue

        # Path B: search void move by ref
        void_ref = 'Void cheque %s' % c.name
        void_move = env['account.move'].search([('ref', '=', void_ref)], limit=1)
        if not void_move:
            _logger.warning(
                "18.0.1.0.13: cheque %s (ID=%s) — Path B: no move with ref '%s'. Skipping.",
                c.name, c.id, void_ref,
            )
            skipped += 1
            continue

        dest_account = c.payment_id.destination_account_id
        if not dest_account:
            _logger.warning(
                "18.0.1.0.13: cheque %s (ID=%s) — Path B: no destination_account_id on payment. Skipping.",
                c.name, c.id,
            )
            skipped += 1
            continue

        void_line_0 = void_move.line_ids.filtered(lambda l: l.account_id == dest_account)
        if not void_line_0:
            _logger.warning(
                "18.0.1.0.13: cheque %s (ID=%s) — Path B: no line on account %s in void move %s. Skipping.",
                c.name, c.id, dest_account.display_name, void_move.name,
            )
            skipped += 1
            continue

        c.outstanding_line_id = void_line_0[0]
        fixed += 1
        _logger.info(
            "18.0.1.0.13: cheque %s (ID=%s) — fixed via Path B (ref search). Move: %s.",
            c.name, c.id, void_move.name,
        )

    _logger.info(
        "Migration 18.0.1.0.13: done. Fixed=%d, Skipped=%d.",
        fixed, skipped,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Step 9 — originally 18.0.1.0.14
# ═══════════════════════════════════════════════════════════════════════════════
def _migrate_1_0_14(env):
    """Fix deposited cheques with outstanding_line_id = False (Group B).

    For each cheque, follows the reconciliation chain to determine correct state:
    - Unreconciled collection line → point outstanding_line_id, keep 'deposit'.
    - Reconciled collection line → follow to asset_cash bank line → 'cashed'.
    """
    from odoo import fields

    cheques = env['account.cheque'].search([
        ('state', '=', 'deposit'),
        ('outstanding_line_id', '=', False),
    ])

    _logger.info(
        "Migration 18.0.1.0.14: %d deposited cheque(s) with NULL outstanding_line_id.",
        len(cheques),
    )

    fixed = 0
    cashed = 0
    skipped = 0

    for c in cheques:
        coll_acc = c.original_journal_id.cheque_collection_account_id
        if not coll_acc:
            _logger.warning(
                "18.0.1.0.14: cheque %s — original journal '%s' has no "
                "cheque_collection_account_id. Skipping.",
                c.name, c.original_journal_id.name,
            )
            skipped += 1
            continue

        if not c.deposit_journal_id:
            _logger.warning(
                "18.0.1.0.14: cheque %s — no deposit_journal_id. Skipping.",
                c.name,
            )
            skipped += 1
            continue

        deposit_move = env['account.move'].search([
            ('journal_id', '=', c.deposit_journal_id.id),
            ('state', '=', 'posted'),
            ('ref', 'ilike', 'Deposit: %s' % c.name),
        ], limit=1, order='date desc, id desc')

        if not deposit_move:
            _logger.warning(
                "18.0.1.0.14: cheque %s — no posted deposit JE found in journal "
                "'%s' with ref matching 'Deposit: %s'. Skipping.",
                c.name, c.deposit_journal_id.name, c.name,
            )
            skipped += 1
            continue

        coll_line = deposit_move.line_ids.filtered(
            lambda l: l.account_id == coll_acc
        )[:1]

        if not coll_line:
            _logger.warning(
                "18.0.1.0.14: cheque %s — deposit JE %s has no line on "
                "collection account %s. Lines: %s. Skipping.",
                c.name, deposit_move.name, coll_acc.code,
                [(l.id, l.account_id.code) for l in deposit_move.line_ids],
            )
            skipped += 1
            continue

        if not coll_line.reconciled:
            c.write({'outstanding_line_id': coll_line.id})
            _logger.info(
                "18.0.1.0.14: cheque %s — outstanding_line_id → %s "
                "(%s, %s). State stays 'deposit'.",
                c.name, coll_line.id, deposit_move.name, coll_acc.code,
            )
            fixed += 1
            continue

        counterpart = coll_line.full_reconcile_id.reconciled_line_ids - coll_line
        bank_line = counterpart.move_id.line_ids.filtered(
            lambda l: l.account_id != coll_acc
                      and not (l.move_id.name or '').startswith('EXCH/')
                      and l.account_id.account_type == 'asset_cash'
        )[:1]

        if bank_line:
            c.write({
                'state': 'cashed',
                'cashed_date': bank_line.date or fields.Date.today(),
                'outstanding_line_id': bank_line.id,
            })
            _logger.info(
                "18.0.1.0.14: cheque %s — CASHED. outstanding_line_id → %s "
                "(%s, account %s). cashed_date=%s.",
                c.name, bank_line.id, bank_line.move_id.name,
                bank_line.account_id.code, bank_line.date,
            )
            cashed += 1
        else:
            _logger.warning(
                "18.0.1.0.14: cheque %s — collection line %s in %s is "
                "reconciled (full_rec=%s) but no asset_cash bank line found "
                "in counterpart moves %s. Needs manual resolution.",
                c.name, coll_line.id, deposit_move.name,
                coll_line.full_reconcile_id.id,
                counterpart.move_id.mapped('name'),
            )
            skipped += 1

    _logger.info(
        "Migration 18.0.1.0.14 complete: %d kept deposit, %d advanced to cashed, "
        "%d skipped.",
        fixed, cashed, skipped,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Step 10 — originally 18.0.1.0.15
# ═══════════════════════════════════════════════════════════════════════════════
def _migrate_1_0_15(env):
    """Fix deposited cheques with NULL outstanding_line_id — warranty state.

    Identifies the correct path:
    - WARRANTY: debit line account != configured collection account
    - DEPOSIT: unreconciled collection line
    - CASHED: reconciled collection line → trace to asset_cash bank line
    """
    from odoo import fields

    cheques = env['account.cheque'].search([
        ('state', '=', 'deposit'),
        ('outstanding_line_id', '=', False),
    ])

    _logger.info(
        "Migration 18.0.1.0.15: %d deposited cheque(s) with NULL outstanding_line_id.",
        len(cheques),
    )

    warranty_count = 0
    deposit_count = 0
    cashed_count = 0
    skipped = 0

    for c in cheques:
        if not c.deposit_journal_id:
            _logger.warning(
                "18.0.1.0.15: cheque %s — no deposit_journal_id. Skipping.",
                c.name,
            )
            skipped += 1
            continue

        deposit_move = env['account.move'].search([
            ('journal_id', '=', c.deposit_journal_id.id),
            ('state', '=', 'posted'),
            ('ref', 'ilike', 'Deposit: %s' % c.name),
        ], limit=1, order='date desc, id desc')

        if not deposit_move:
            _logger.warning(
                "18.0.1.0.15: cheque %s — no posted deposit JE found in journal "
                "'%s' with ref matching 'Deposit: %s'. Skipping.",
                c.name, c.deposit_journal_id.name, c.name,
            )
            skipped += 1
            continue

        outstanding_acc = c.payment_id.outstanding_account_id
        if not outstanding_acc:
            _logger.warning(
                "18.0.1.0.15: cheque %s — payment %s has no outstanding_account_id. Skipping.",
                c.name, c.payment_id.name,
            )
            skipped += 1
            continue

        coll_line = deposit_move.line_ids.filtered(
            lambda l: l.account_id != outstanding_acc
        )[:1]

        if not coll_line:
            _logger.warning(
                "18.0.1.0.15: cheque %s — deposit JE %s has no line outside "
                "outstanding account %s. Lines: %s. Skipping (malformed JE).",
                c.name, deposit_move.name, outstanding_acc.code,
                [(l.id, l.account_id.code) for l in deposit_move.line_ids],
            )
            skipped += 1
            continue

        coll_acc = c.original_journal_id.cheque_collection_account_id

        if coll_line.account_id != coll_acc:
            # ── WARRANTY path ────────────────────────────────────────────
            c.write({
                'state': 'warranty',
                'outstanding_line_id': coll_line.id,
            })
            deposit_move.write({
                'ref': 'Warranty: %s' % c.name,
            })
            _logger.info(
                "18.0.1.0.15: cheque %s — WARRANTY. outstanding_line_id → %s "
                "(%s, account %s). Move ref → 'Warranty: %s'.",
                c.name, coll_line.id, deposit_move.name,
                coll_line.account_id.code, c.name,
            )
            warranty_count += 1

        elif not coll_line.reconciled:
            # ── DEPOSIT path ─────────────────────────────────────────────
            c.write({'outstanding_line_id': coll_line.id})
            _logger.info(
                "18.0.1.0.15: cheque %s — DEPOSIT. outstanding_line_id → %s "
                "(%s, account %s).",
                c.name, coll_line.id, deposit_move.name,
                coll_line.account_id.code,
            )
            deposit_count += 1

        else:
            # ── CASHED path ──────────────────────────────────────────────
            counterpart = coll_line.full_reconcile_id.reconciled_line_ids - coll_line
            bank_line = counterpart.move_id.line_ids.filtered(
                lambda l: l.account_id != coll_line.account_id
                          and not (l.move_id.name or '').startswith('EXCH/')
                          and l.account_id.account_type == 'asset_cash'
            )[:1]

            if bank_line:
                c.write({
                    'state': 'cashed',
                    'cashed_date': bank_line.date or fields.Date.today(),
                    'outstanding_line_id': bank_line.id,
                })
                _logger.info(
                    "18.0.1.0.15: cheque %s — CASHED. outstanding_line_id → %s "
                    "(%s, account %s). cashed_date=%s.",
                    c.name, bank_line.id, bank_line.move_id.name,
                    bank_line.account_id.code, bank_line.date,
                )
                cashed_count += 1
            else:
                _logger.warning(
                    "18.0.1.0.15: cheque %s — collection line %s in %s is "
                    "reconciled (full_rec=%s) but no asset_cash bank line found "
                    "in counterpart moves %s. Needs manual resolution.",
                    c.name, coll_line.id, deposit_move.name,
                    coll_line.full_reconcile_id.id,
                    counterpart.move_id.mapped('name'),
                )
                skipped += 1

    _logger.info(
        "Migration 18.0.1.0.15 complete: %d warranty, %d deposit, %d cashed, "
        "%d skipped.",
        warranty_count, deposit_count, cashed_count, skipped,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Step 11 — originally 18.0.1.0.16
# ═══════════════════════════════════════════════════════════════════════════════
def _migrate_1_0_16(env):
    """Fix deposited cheques whose outstanding_line_id points to an EXCH move (Group A).

    Traces the reconciliation chain from the real collection line in the deposit
    JE to find the asset_cash bank line, then advances to state='cashed'.
    """
    from odoo import fields

    deposited = env['account.cheque'].search([
        ('state', '=', 'deposit'),
        ('outstanding_line_id', '!=', False),
    ])

    broken = deposited.filtered(
        lambda c: (c.outstanding_line_id.move_id.name or '').startswith('EXCH/')
    )

    _logger.info(
        "Migration 18.0.1.0.16: %d deposited cheque(s) with EXCH outstanding_line_id.",
        len(broken),
    )

    cashed_count = 0
    deposit_count = 0
    skipped = 0

    for c in broken:
        coll_acc = c.original_journal_id.cheque_collection_account_id
        if not coll_acc:
            _logger.warning(
                "18.0.1.0.16: cheque %s — original journal '%s' has no "
                "cheque_collection_account_id. Skipping.",
                c.name, c.original_journal_id.name,
            )
            skipped += 1
            continue

        if not c.deposit_journal_id:
            _logger.warning(
                "18.0.1.0.16: cheque %s — no deposit_journal_id. Skipping.",
                c.name,
            )
            skipped += 1
            continue

        deposit_move = env['account.move'].search([
            ('journal_id', '=', c.deposit_journal_id.id),
            ('state', '=', 'posted'),
            ('ref', 'ilike', 'Deposit: %s' % c.name),
        ], limit=1, order='date desc, id desc')

        if not deposit_move:
            _logger.warning(
                "18.0.1.0.16: cheque %s — no posted deposit JE found in journal "
                "'%s' with ref matching 'Deposit: %s'. Skipping.",
                c.name, c.deposit_journal_id.name, c.name,
            )
            skipped += 1
            continue

        coll_line = deposit_move.line_ids.filtered(
            lambda l: l.account_id == coll_acc
        )[:1]

        if not coll_line:
            _logger.warning(
                "18.0.1.0.16: cheque %s — deposit JE %s has no line on "
                "collection account %s. Lines: %s. Skipping.",
                c.name, deposit_move.name, coll_acc.code,
                [(l.id, l.account_id.code) for l in deposit_move.line_ids],
            )
            skipped += 1
            continue

        if not coll_line.reconciled:
            c.write({'outstanding_line_id': coll_line.id})
            _logger.info(
                "18.0.1.0.16: cheque %s — collection line unreconciled. "
                "outstanding_line_id → %s (%s, %s). State stays 'deposit'.",
                c.name, coll_line.id, deposit_move.name, coll_acc.code,
            )
            deposit_count += 1
            continue

        counterpart = coll_line.full_reconcile_id.reconciled_line_ids - coll_line
        bank_line = counterpart.move_id.line_ids.filtered(
            lambda l: l.account_id != coll_acc
                      and not (l.move_id.name or '').startswith('EXCH/')
                      and l.account_id.account_type == 'asset_cash'
        )[:1]

        if bank_line:
            c.write({
                'state': 'cashed',
                'cashed_date': bank_line.date or fields.Date.today(),
                'outstanding_line_id': bank_line.id,
            })
            _logger.info(
                "18.0.1.0.16: cheque %s — CASHED. outstanding_line_id → %s "
                "(%s, account %s). cashed_date=%s.",
                c.name, bank_line.id, bank_line.move_id.name,
                bank_line.account_id.code, bank_line.date,
            )
            cashed_count += 1
        else:
            _logger.warning(
                "18.0.1.0.16: cheque %s — collection line %s in %s is "
                "reconciled (full_rec=%s) but no asset_cash bank line found "
                "in counterpart moves %s. Needs manual resolution.",
                c.name, coll_line.id, deposit_move.name,
                coll_line.full_reconcile_id.id,
                counterpart.move_id.mapped('name'),
            )
            skipped += 1

    _logger.info(
        "Migration 18.0.1.0.16 complete: %d cashed, %d kept deposit, %d skipped.",
        cashed_count, deposit_count, skipped,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Step 12 — originally 18.0.1.0.17
# ═══════════════════════════════════════════════════════════════════════════════
def _migrate_1_0_17(env):
    """Fix deposited cheques with EXCH outstanding_line_id skipped by mig16.

    These are warranty cases: deposit JE debited 126000 (warranty) / credited
    101010 (outstanding). Apply WARRANTY path — set state to 'warranty', point
    outstanding_line_id to the 126000 line, and rename the deposit JE ref.
    """
    deposited = env['account.cheque'].search([
        ('state', '=', 'deposit'),
        ('outstanding_line_id', '!=', False),
    ])

    broken = deposited.filtered(
        lambda c: (c.outstanding_line_id.move_id.name or '').startswith('EXCH/')
    )

    _logger.info(
        "Migration 18.0.1.0.17: %d deposited cheque(s) with EXCH outstanding_line_id.",
        len(broken),
    )

    warranty_count = 0
    skipped = 0

    for c in broken:
        if not c.deposit_journal_id:
            _logger.warning(
                "18.0.1.0.17: cheque %s — no deposit_journal_id. Skipping.",
                c.name,
            )
            skipped += 1
            continue

        deposit_move = env['account.move'].search([
            ('journal_id', '=', c.deposit_journal_id.id),
            ('state', '=', 'posted'),
            ('ref', 'ilike', 'Deposit: %s' % c.name),
        ], limit=1, order='date desc, id desc')

        if not deposit_move:
            _logger.warning(
                "18.0.1.0.17: cheque %s — no posted deposit JE found in journal "
                "'%s' with ref matching 'Deposit: %s'. Skipping.",
                c.name, c.deposit_journal_id.name, c.name,
            )
            skipped += 1
            continue

        outstanding_acc = c.payment_id.outstanding_account_id
        if not outstanding_acc:
            _logger.warning(
                "18.0.1.0.17: cheque %s — payment %s has no outstanding_account_id. Skipping.",
                c.name, c.payment_id.name,
            )
            skipped += 1
            continue

        transfer_line = deposit_move.line_ids.filtered(
            lambda l: l.account_id != outstanding_acc
        )[:1]

        if not transfer_line:
            _logger.warning(
                "18.0.1.0.17: cheque %s — deposit JE %s has no line outside "
                "outstanding account %s. Lines: %s. Skipping.",
                c.name, deposit_move.name, outstanding_acc.code,
                [(l.id, l.account_id.code) for l in deposit_move.line_ids],
            )
            skipped += 1
            continue

        c.write({
            'state': 'warranty',
            'outstanding_line_id': transfer_line.id,
        })
        deposit_move.write({
            'ref': 'Warranty: %s' % c.name,
        })
        _logger.info(
            "18.0.1.0.17: cheque %s — WARRANTY. outstanding_line_id → %s "
            "(%s, account %s). Move ref → 'Warranty: %s'.",
            c.name, transfer_line.id, deposit_move.name,
            transfer_line.account_id.code, c.name,
        )
        warranty_count += 1

    _logger.info(
        "Migration 18.0.1.0.17 complete: %d warranty, %d skipped.",
        warranty_count, skipped,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Step 13 — originally 18.0.1.0.18
# ═══════════════════════════════════════════════════════════════════════════════
def _migrate_1_0_18(env):
    """Fix deposited cheques whose outstanding_line_id points to the reconciled credit line.

    For each affected cheque:
      - Locate the deposit move via outstanding_line_id.move_id
      - Pick the unreconciled debit line on that move
      - Update outstanding_line_id
    """
    broken = env['account.cheque'].search([
        ('state', '=', 'deposit'),
        ('outstanding_line_id', '!=', False),
        ('outstanding_line_id.reconciled', '=', True),
    ])

    if not broken:
        _logger.info("Migration 18.0.1.0.18: no deposited cheques with stale outstanding_line_id.")
        return

    _logger.info(
        "Migration 18.0.1.0.18: found %d deposited cheque(s) with reconciled outstanding_line_id.",
        len(broken),
    )

    fixed = 0
    skipped = 0

    for cheque in broken:
        deposit_move = cheque.outstanding_line_id.move_id
        correct_line = deposit_move.line_ids.filtered(
            lambda l: not l.reconciled and l.debit > 0
        )[:1]

        if not correct_line:
            _logger.warning(
                "Migration 18.0.1.0.18: cheque %s (ID=%s) — no unreconciled debit line "
                "found on move %s (ID=%s). Skipping.",
                cheque.name, cheque.id, deposit_move.name, deposit_move.id,
            )
            skipped += 1
            continue

        old_line = cheque.outstanding_line_id
        cheque.write({'outstanding_line_id': correct_line.id})
        _logger.info(
            "Migration 18.0.1.0.18: cheque %s (ID=%s) — outstanding_line_id fixed: "
            "%s (account %s, reconciled) → %s (account %s, open).",
            cheque.name, cheque.id,
            old_line.id, old_line.account_id.display_name,
            correct_line.id, correct_line.account_id.display_name,
        )
        fixed += 1

    _logger.info(
        "Migration 18.0.1.0.18: done. Fixed %d, skipped %d.",
        fixed, skipped,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════════════════════
def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})

    steps = [
        _migrate_1_0_5,
        _migrate_1_0_6,
        _migrate_1_0_8,
        _migrate_1_0_9,
        _migrate_1_0_10,
        _migrate_1_0_11,
        _migrate_1_0_12,
        _migrate_1_0_13,
        _migrate_1_0_14,
        _migrate_1_0_15,
        _migrate_1_0_16,
        _migrate_1_0_17,
        _migrate_1_0_18,
    ]
    for step in steps:
        _logger.info("Running %s...", step.__name__)
        step(env)
        env.invalidate_all()  # clear ORM cache between steps
