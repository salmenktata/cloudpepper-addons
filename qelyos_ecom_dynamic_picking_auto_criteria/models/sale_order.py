# -*- coding: utf-8 -*-
from odoo import models, api

class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.model
    def _get_available_qty(self, product, location):
        return self.env['stock.quant']._get_available_quantity(product, location)

    def _score_location_for_picking(self, picking, loc):
        # Score = min des dispos parmi toutes les lignes du picking
        if not picking.move_ids_without_package:
            return 0.0
        return min(self._get_available_qty(m.product_id, loc) for m in picking.move_ids_without_package)

    def _apply_source_location(self, picking, chosen_loc, strategy, detail=None):
        picking.location_id = chosen_loc.id
        for move in picking.move_ids_without_package:
            move.location_id = chosen_loc.id
        try:
            picking.action_assign()
        except Exception:
            picking.action_unreserve()
            picking.action_assign()
        msg = f"Source définie sur {chosen_loc.display_name} (stratégie: {strategy})"
        if detail:
            msg += f"<br/>{detail}"
        picking.message_post(body=msg)

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
            picking_vals = {
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
            }
            StockPicking.create(picking_vals)

    def _action_confirm(self):
        res = super()._action_confirm()
        for order in self:
            company = order.company_id
            website_limit = company.ecom_dynamic_website_id
            if not order.website_id or (website_limit and order.website_id != website_limit):
                continue

            locations = company.ecom_dynamic_source_location_ids
            strategy = company.ecom_dynamic_strategy
            if not locations or strategy not in ('central_then_maxstock_then_order','first_available','most_available'):
                continue

            pickings = order.picking_ids.filtered(lambda p: p.picking_type_code == 'outgoing')
            for picking in pickings:
                chosen_loc = None
                detail = ""

                if strategy == 'central_then_maxstock_then_order':
                    # 1) CENTRAL full cover ?
                    central_candidates = locations.filtered(
                        lambda l: 'CENT' in (l.complete_name or l.display_name or '').upper() or 'CENTRAL' in (l.complete_name or l.display_name or '').upper()
                    )
                    central = central_candidates[:1]
                    if central:
                        c = central[0]
                        if all(self._get_available_qty(m.product_id, c) >= m.product_uom_qty for m in picking.move_ids_without_package):
                            chosen_loc = c
                            detail = "Critère 1: CENTRAL couvre toute la commande"

                    # 2) sinon max stock parmi Gafsa/Sousse/Tunis
                    if not chosen_loc:
                        names = ['GAFSA','SOUSSE','TUNIS']
                        gst_locations = [l for l in locations if any(n in (l.complete_name or l.display_name or '').upper() for n in names)]
                        if gst_locations:
                            scored = [(l, self._score_location_for_picking(picking, l)) for l in gst_locations]
                            if scored:
                                best = max(scored, key=lambda x: x[1])
                                if best[1] > 0:
                                    chosen_loc = best[0]
                                    detail = f"Critère 2: Max stock parmi Gafsa/Sousse/Tunis → {chosen_loc.display_name} (score={best[1]})"

                    # 3) sinon ordre fixe Gafsa > Sousse > Tunis
                    if not chosen_loc:
                        for nm in ['GAFSA','SOUSSE','TUNIS']:
                            loc = next((l for l in locations if nm in (l.complete_name or l.display_name or '').upper()), None)
                            if loc:
                                chosen_loc = loc
                                detail = f"Critère 3: Ordre fixe → {loc.display_name}"
                                break

                elif strategy == 'first_available':
                    for loc in locations:
                        if all(self._get_available_qty(m.product_id, loc) >= m.product_uom_qty for m in picking.move_ids_without_package):
                            chosen_loc = loc
                            detail = "Stratégie: premier emplacement couvrant"
                            break

                elif strategy == 'most_available':
                    scored = [(l, self._score_location_for_picking(picking, l)) for l in locations]
                    if scored:
                        chosen_loc = max(scored, key=lambda x: x[1])[0]
                        detail = f"Stratégie: plus de stock → {chosen_loc.display_name}"

                if chosen_loc:
                    fully_covers = all(self._get_available_qty(m.product_id, chosen_loc) >= m.product_uom_qty
                                       for m in picking.move_ids_without_package)
                    if not fully_covers:
                        self._create_internal_transfer(chosen_loc, picking.move_ids_without_package)
                    self._apply_source_location(picking, chosen_loc, strategy, detail=detail)

        return res
