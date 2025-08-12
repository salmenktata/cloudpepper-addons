# -*- coding: utf-8 -*-
from odoo import models, api

BOUTIQUE_NAMES = ['BOUTIQUE GAFSA', 'BOUTIQUE SOUSSE', 'BOUTIQUE SOUKRA']

class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.model
    def _get_available_qty(self, product, location):
        return self.env['stock.quant']._get_available_quantity(product, location)

    def _score_location_for_picking(self, picking, loc):
        if not picking.move_ids_without_package:
            return 0.0
        return min(self._get_available_qty(m.product_id, loc) for m in picking.move_ids_without_package)

    def _apply_source_location(self, picking, chosen_loc, reason):
        old_src = picking.location_id.display_name if picking.location_id else "N/A"
        picking.location_id = chosen_loc.id
        for move in picking.move_ids_without_package:
            move.location_id = chosen_loc.id
        try:
            picking.action_assign()
        except Exception:
            picking.action_unreserve()
            picking.action_assign()
        picking.message_post(body=f"Source forcée: {old_src} → <b>{chosen_loc.display_name}</b><br/>{reason}")

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

    def _warehouse_key_locs(self, picking):
        wh = picking.picking_type_id.warehouse_id or self.env['stock.warehouse'].search([('company_id','=',picking.company_id.id)], limit=1)
        if not wh:
            return {}
        return {
            'stock': wh.lot_stock_id,
            'output': getattr(wh, 'wh_output_stock_loc_id', False),
            'pack': getattr(wh, 'wh_pack_stock_loc_id', False),
            'input': getattr(wh, 'wh_input_stock_loc_id', False),
        }

    def _classify_delivery_step(self, picking):
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

    def _choose_location_for_picking(self, company, picking):
        # Only INTERNAL locations
        locations = company.ecom_dynamic_source_location_ids.filtered(lambda l: l.usage == 'internal')
        if not locations:
            return None, ""
        strategy = company.ecom_dynamic_strategy
        lines = picking.move_ids_without_package

        wh_locs = self._warehouse_key_locs(picking)
        central_loc = wh_locs.get('stock')
        if central_loc and central_loc not in locations:
            locations |= central_loc

        if strategy == 'central_then_boutiques_max_then_order':
            # Step 1: CENTRAL (DISPONIBLE)
            if central_loc:
                if all(self._get_available_qty(m.product_id, central_loc) >= m.product_uom_qty for m in lines):
                    return central_loc, "Critère 1 (DISPONIBLE): CENTRAL couvre toute la commande"

            # Step 2: Max dispo parmi les 3 boutiques (Gafsa/Sousse/Soukra)
            def is_boutique(loc):
                name = (loc.complete_name or loc.display_name or '').upper()
                return any(key in name for key in BOUTIQUE_NAMES)

            boutique_locs = [l for l in locations if is_boutique(l)]
            if boutique_locs:
                scored = [(l, self._score_location_for_picking(picking, l)) for l in boutique_locs]
                if scored:
                    best = max(scored, key=lambda x: x[1])
                    if best[1] > 0:
                        return best[0], f"Critère 2: Max dispo (boutiques) → {best[0].display_name} (score={best[1]})"

            # Step 3: Ordre fixe Gafsa > Sousse > Soukra
            for nm in ['BOUTIQUE GAFSA', 'BOUTIQUE SOUSSE', 'BOUTIQUE SOUKRA']:
                loc = next((l for l in locations if nm in (l.complete_name or l.display_name or '').upper()), None)
                if loc:
                    return loc, f"Critère 3: Ordre fixe → {loc.display_name}"

        elif strategy == 'first_available':
            for loc in locations:
                if all(self._get_available_qty(m.product_id, loc) >= m.product_uom_qty for m in lines):
                    return loc, "Stratégie: premier emplacement couvrant"

        elif strategy == 'most_available':
            scored = [(l, self._score_location_for_picking(picking, l)) for l in locations]
            if scored:
                best = max(scored, key=lambda x: x[1])
                return best[0], f"Stratégie: plus de stock → {best[0].display_name} (score={best[1]})"

        return None, ""

    def _action_confirm(self):
        res = super()._action_confirm()
        for order in self:
            company = order.company_id
            website_limit = company.ecom_dynamic_website_id
            if not order.website_id or (website_limit and order.website_id != website_limit):
                continue

            pickings = order.picking_ids
            if not pickings:
                continue

            # Choose leg: 3-step pick > 2-step pick > 1-step outgoing
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
                chosen_loc, reason = self._choose_location_for_picking(company, picking)
                if not chosen_loc:
                    continue
                fully_covers = all(self._get_available_qty(m.product_id, chosen_loc) >= m.product_uom_qty
                                   for m in picking.move_ids_without_package)
                if not fully_covers:
                    self._create_internal_transfer(chosen_loc, picking.move_ids_without_package)
                self._apply_source_location(picking, chosen_loc, reason + " | Flux 1/2/3 étapes.")
        return res
