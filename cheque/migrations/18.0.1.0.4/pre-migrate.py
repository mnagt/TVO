"""Migrate collection_line_id → outstanding_line_id for deposit/warranty/cashed cheques."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Check if column still exists (it will be dropped by ORM after this migration)
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'account_cheque' AND column_name = 'collection_line_id'
    """)
    if not cr.fetchone():
        _logger.info("collection_line_id column already removed, skipping migration.")
        return

    cr.execute("""
        UPDATE account_cheque
        SET outstanding_line_id = collection_line_id
        WHERE collection_line_id IS NOT NULL
          AND state IN ('deposit', 'warranty', 'cashed')
    """)
    count = cr.rowcount
    _logger.info(
        "Migrated %d cheque(s): outstanding_line_id = collection_line_id "
        "for deposit/warranty/cashed states.",
        count,
    )
