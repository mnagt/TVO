def migrate(cr, version):
    cr.execute("""
        ALTER TABLE res_company
        ADD COLUMN IF NOT EXISTS tl_general_ledger boolean DEFAULT false
    """)