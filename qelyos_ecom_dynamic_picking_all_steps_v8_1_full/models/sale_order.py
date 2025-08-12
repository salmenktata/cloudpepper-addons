
# -*- coding: utf-8 -*-
from odoo import models, api

class SaleOrder(models.Model):
    _inherit = "sale.order"

    # ----- Quantities helpers -----
    @api.model
    def _get_available_qty(self, product, location):
        # Available quantity = excludes reservations, includes children
        return self.env['stock.quant']._get_available_quantity(product, location)

    def _score_location_for_picking(self, picking, loc):
        # Score = min available across lines (guarantees single-source coverage if >= required per line)
        if not picking.move_ids_without_package:
            return 0.0
        return min(self._get_available_qty(m.product_id, loc) for m in picking.move_ids_without_package)

    # ----- Apply choice -----
    def _apply_source_location(self, picking, chosen_loc, reason, debug_table_lines):
        old_src = picking.location_id.display_name if picking.location_id else "N/A"
        # Update picking + moves
        picking.location_id = chosen_loc.id
        for move in picking.move_ids_without_package:
            move.location_id = chosen_loc.id
        # (Re)assign reservations
        try:
            picking.action_assign()
        except Exception:
            picking.action_unreserve()
            picking.action_assign()

        # Build plain-text log
        lines = [ "[Dynamic Picking]",
                  f"Source forcée: {old_src} → {chosen_loc.display_name}",
                  reason, "",
                  "Disponibilités :" ]
        lines.extend([f"  - {name} : {qty}" for name, qty in debug_table_lines])
        message = "\n".join(lines)

        # Post to picking chatter only (V8.1)
        picking.message_post(body=message)

    # ----- Internal transfer helper -----
    def _find_internal_picking_type(self, source_loc_id, dest_loc_id):
        return self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('default_location_src_id', '=', source_loc_id),
            ('default_location_dest_id', '=', dest_loc_id)
        ], limit=1)

    def _create_internal_transfer(self, dest_location, moves):
        StockPicking = self.env['stock.picking']
        for move in moves:
            quant = self.env['stock.quant'].search([
                ('product_id', '=', move.product_id.id),
                ('quantity', '>=', move.product_uom_qty)
            ], limit=1)
            source_loc = quant.location_id
            if not source_loc or source_loc == dest_location:
                continue
            picking_type = self._find_internal_picking_type(source_loc.id, dest_location.id)
            if not picking_type:
                continue
            StockPicking.create({
                'picking_type_id': picking_type.id,
                'location_id': source_loc.id,
                'location_dest_id': dest_location.id,
                'move_ids_without_package': [(0, 0, {
                    'name': move.product_id.display_name,
                    'product_id': move.product_id.id,
                    'product_uom_qty': move.product_uom_qty,
                    'product_uom': move.product_uom.id,
                    'location_id': source_loc.id,
                    'location_dest_id': dest_location.id,
                })]
            })

    # ----- Warehouse helpers -----
    def _warehouse_key_locs(self, picking):
        wh = picking.picking_type_id.warehouse_id or self.env['stock.warehouse'].search([('company_id','=',picking.company_id.id)], limit=1)
        if not wh:
            return {}
        return {
            'stock': wh.lot_stock_id,
            'output': getattr(wh, 'wh_output_stock_loc_id', False),
            'pack': getattr(wh, 'wh_pack_stock_loc_id', False),
        }

    def _classify_delivery_step(self, picking):
        # Detect which leg to modify
        if picking.picking_type_code == 'outgoing':
            return 'outgoing'
        if picking.picking_type_code == 'internal':
            locs = self._warehouse_key_locs(picking)
            src = picking.location_id
            dst = picking.location_dest_id
            if locs.get('stock') and locs.get('output') and src == locs['stock'] and dst == locs['output']:
                return 'two_step_pick'
            if locs.get('stock') and locs.get('pack') and src == locs['stock'] and dst == locs['pack']:
                return 'three_step_pick'
        return None

    # ----- Choose location according to V8.1 rules -----
    def _choose_location_for_picking(self, company, picking):
        # Filter internal locations only
        locations = company.ecom_dynamic_source_location_ids.filtered(lambda l: l.usage == 'internal')
        if not locations:
            return None, "", []

        lines = picking.move_ids_without_package
        # Identify central stock from warehouse
        wh_locs = self._warehouse_key_locs(picking)
        central_loc = wh_locs.get('stock')

        # Prepare availability table (plain text)
        debug = []
        # CENTRAL first (if exists)
        if central_loc:
            total = 0.0
            for m in lines:
                total = self._get_available_qty(m.product_id, central_loc)
            debug.append((central_loc.display_name, total))

        # Then all listed locations (ensure uniqueness)
        seen = set()
        if central_loc:
            seen.add(central_loc.id)
        for loc in locations:
            if loc.id in seen:
                continue
            qty = 0.0
            for m in lines:
                qty = self._get_available_qty(m.product_id, loc)
            debug.append((loc.display_name, qty))
            seen.add(loc.id)

        strategy = company.ecom_dynamic_strategy

        # Build boutiques list = all listed locations EXCEPT central (maintain user's order)
        boutiques = [l for l in locations if not central_loc or l.id != central_loc.id]

        # --- Criterion 1: CENTRAL available covers all ---
        if strategy == 'central_then_max_all_then_order' and central_loc:
            if all(self._get_available_qty(m.product_id, central_loc) >= m.product_uom_qty for m in lines):
                return central_loc, "Critère 1 (DISPONIBLE): CENTRAL couvre toute la commande", debug

        # --- Criterion 2: Max available among ALL boutiques ---
        if strategy == 'central_then_max_all_then_order' and boutiques:
            scored = [(l, self._score_location_for_picking(picking, l)) for l in boutiques]
            if scored:
                best = max(scored, key=lambda x: x[1])
                if best[1] > 0:
                    return best[0], f"Critère 2: Max dispo boutiques → {best[0].display_name} (score={best[1]})", debug

        # --- Criterion 3: Strict order (from settings order) ---
        # choose the first boutique that fully covers; if none covers, pick first and create restock later
        for loc in boutiques:
            if all(self._get_available_qty(m.product_id, loc) >= m.product_uom_qty for m in lines):
                return loc, f"Critère 3: Ordre strict → {loc.display_name}", debug

        # None covers: fallback to first boutique if exists (restock will be created)
        if boutiques:
            return boutiques[0], f"Critère 3: Ordre strict (aucune dispo) → {boutiques[0].display_name}", debug

        # If nothing else, return None
        return None, "", debug

    # ----- Main hook -----
    def _action_confirm(self):
        res = super()._action_confirm()
        for order in self:
            company = order.company_id
            website_limit = company.ecom_dynamic_website_id
            if not order.website_id or (website_limit and order.website_id != website_limit):
                continue

            if company.ecom_dynamic_strategy == 'default_only':
                continue

            pickings = order.picking_ids
            if not pickings:
                continue

            # Choose target leg: 3-step pick > 2-step pick > 1-step outgoing
            target = None
            for p in pickings:
                if self._classify_delivery_step(p) == 'three_step_pick':
                    target = p
                    break
            if not target:
                for p in pickings:
                    if self._classify_delivery_step(p) == 'two_step_pick':
                        target = p
                        break
            if not target:
                target = pickings.filtered(lambda p: p.picking_type_code == 'outgoing')[:1]

            if not target:
                continue

            for picking in target:
                chosen_loc, reason, debug_table = self._choose_location_for_picking(company, picking)
                if not chosen_loc:
                    continue
                # If chosen location doesn't fully cover on available qty, create internal transfer
                fully_covers = all(self._get_available_qty(m.product_id, chosen_loc) >= m.product_uom_qty
                                   for m in picking.move_ids_without_package)
                if not fully_covers:
                    self._create_internal_transfer(chosen_loc, picking.move_ids_without_package)
                    reason += " | Réassort interne créé (couverture incomplète)."

                # Apply and log (plain text; V8.1 = picking only)
                self._apply_source_location(picking, chosen_loc, reason, debug_table)

        return res
