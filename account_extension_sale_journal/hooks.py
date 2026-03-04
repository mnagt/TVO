def post_init_hook(env):
    """Backfill sale_order_id for stock-originated journal lines."""
    env.cr.execute("""
        UPDATE account_move_line aml
        SET sale_order_id = sol.order_id
        FROM account_move am
        INNER JOIN stock_move sm ON sm.id = am.stock_move_id
        INNER JOIN sale_order_line sol ON sol.id = sm.sale_line_id
        WHERE aml.move_id = am.id
          AND sm.sale_line_id IS NOT NULL
          AND aml.sale_order_id IS NULL;
    """)