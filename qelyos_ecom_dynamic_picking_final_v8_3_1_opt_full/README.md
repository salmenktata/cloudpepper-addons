Qelyos eCommerce Dynamic Picking (v8.3.1 Optimized)
===================================================
- Stored compute for badge (less recomputation)
- DB index on stock_move(picking_id, sequence, state)
- Batch-friendly strict order check
- Optional profiling with context {'qelyos_profile': True}
