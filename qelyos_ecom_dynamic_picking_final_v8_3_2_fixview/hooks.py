def post_init_hook(cr, registry):
    cr.execute("""
    CREATE INDEX IF NOT EXISTS idx_stock_move_picking_seq_state
    ON stock_move (picking_id, sequence, state);
    """)
