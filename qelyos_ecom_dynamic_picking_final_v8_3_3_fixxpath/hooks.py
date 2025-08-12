# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID
import logging
_logger = logging.getLogger(__name__)

INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_stock_move_picking_seq_state
ON stock_move (picking_id, sequence, state);
"""

def post_init_hook(cr, registry):
    try:
        cr.execute(INDEX_SQL)
        _logger.info("Qelyos: created index idx_stock_move_picking_seq_state")
    except Exception as e:
        _logger.warning("Qelyos: failed to create index (may already exist): %s", e)
