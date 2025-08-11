# -*- coding: utf-8 -*-
from odoo import models, api

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
        # Update picking + moves
        picking.location_id = chosen_loc.id
        for move in picking.move_ids_without_package:
            move.location_id = chosen_loc.id
        # Re-assign reservations
        try:
            picking.action_assign()
        except Exception:
            picking.action_unreserve()
            picking.action_assign()
        picking.message_post(body=(
            f"Route ignorée / source forcée: {old_src} → <b>{chosen_loc.display_name}</b><br/>{reason}"
        ))

    def _choose_location_for_order(self, order, locations, picking):
        company = order.company_id
        strategy = company.ecom_dynamic_strategy
        lines = picking.move_ids_without_package
        chosen_loc = None
        reason = ""

        if strategy == 'central_then_maxstock_then_order':
            # 1) CENTRAL full cover ?
            central_candidates = locations.filtered(
                lambda l: 'CENT' in (l.complete_name or l.display_name or '').upper() or
                          'CENTRAL' in (l.complete_name or l.display_name or '').upper()
            )
            central = central_candidates[:1]
            if central:
                c = central[0]
                if all(self._get_available_qty(m.product_id, c) >= m.product_uom_qty for m in lines):
                    chosen_loc = c
                    reason = "Critère 1: CENTRAL couvre toute la commande"
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
                            reason = f"Critère 2: Max stock Gafsa/Sousse/Tunis → {chosen_loc.display_name} (score={best[1]})"
            # 3) sinon ordre fixe
            if not chosen_loc:
                for nm in ['GAFSA','SOUSSE','TUNIS']:
                    loc = next((l for l in locations if nm in (l.complete_name or l.display_name or '').upper()), None)
                    if loc:
                        chosen_loc = loc
                        reason = f"Critère 3: Ordre fixe → {loc.display_name}"
                        break

        elif strategy == 'most_available':
            scored = [(l, self._score_location_for_picking(picking, l)) for l in locations]
            if scored:
                chosen_loc = max(scored, key=lambda x: x[1])[0]
                reason = f"Stratégie: plus de stock → {chosen_loc.display_name}"
        elif strategy == 'first_available':
            for loc in locations:
                if all(self._get_available_qty(m.product_id, loc) >= m.product_uom_qty for m in lines):
                    chosen_loc = loc
                    reason = "Stratégie: premier emplacement couvrant"
                    break

        return chosen_loc, reason

    def _action_confirm(self):
        # After routes applied by super(), force source on the relevant picking
        res = super()._action_confirm()
        for order in self:
            company = order.company_id
            website_limit = company.ecom_dynamic_website_id
            if not order.website_id or (website_limit and order.website_id != website_limit):
                continue

            # Candidate locations: INTERNAL only
            locations = company.ecom_dynamic_source_location_ids.filtered(lambda l: l.usage == 'internal')
            if not locations:
                continue

            # All pickings of the SO
            pickings = order.picking_ids

            # If there is at least one INTERNAL picking (2-step), we apply the source on INTERNAL only.
            internal_pickings = pickings.filtered(lambda p: p.picking_type_code == 'internal')
            outgoing_pickings = pickings.filtered(lambda p: p.picking_type_code == 'outgoing')

            target_pickings = internal_pickings if internal_pickings else outgoing_pickings

            for picking in target_pickings:
                chosen_loc, reason = self._choose_location_for_order(order, locations, picking)
                if chosen_loc:
                    self._apply_source_location(picking, chosen_loc, reason + " | Forçage pour affichage 'De/Vers'.")
        return res
