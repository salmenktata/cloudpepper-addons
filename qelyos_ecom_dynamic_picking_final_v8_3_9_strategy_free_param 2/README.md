# Qelyos – Dynamic Picking (Final v8.3.9)

This module adds:
- Global IN/OUT 1–2–3 steps selectors (apply to all warehouses via a button)
- Strict operation order (block validate if a lower sequence related picking is open)
- Dual-log (extra messages on create/assign/validate)
- Strategy-free parameters and optional restriction of source locations for OUT pickings
- Internal transfers are unaffected; you can still create them without special types.

## Usage
1. Go to Settings → Inventory → Qelyos – eCommerce Dynamic Picking.
2. Choose IN/OUT steps and click **Apply now** to set all warehouses.
3. (Optional) Enable **Strict order** and/or **Dual log**.
4. (Optional) Set allowed source locations; domain will restrict `location_id` on pickings.
5. If **Only for eCommerce** is checked, dynamic behaviors are applied primarily around website orders.

Tested on Odoo 18 open-source (community).