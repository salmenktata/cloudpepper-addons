# -*- coding: utf-8 -*-
from odoo import models, api

class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.model
    def _get_available_qty(self, product, location):
        return self.env['stock.quant']._get_available_quantity(product, location)

    def _score_location_for_picking(self, picking, loc):
        """Score = quantité minimale disponible sur l'ensemble des lignes du picking pour cet emplacement.
        Garantit que si score >= quantité requise de chaque ligne, l'emplacement couvre tout le picking.
        """
        if not picking.move_ids_without_package:
            return 0.0
        quants = []
        for m in picking.move_ids_without_package:
            quants.append(self._get_available_qty(m.product_id, loc))
        return min(quants) if quants else 0.0

    def _apply_source_location(self, picking, chosen_loc, strategy):
        picking.location_id = chosen_loc.id
        for move in picking.move_ids_without_package:
            move.location_id = chosen_loc.id
        try:
            picking.action_assign()
        except Exception:
            picking.action_unreserve()
            picking.action_assign()
        picking.message_post(body=f"Source définie sur {chosen_loc.display_name} (stratégie: {strategy})")

    def _action_confirm(self):
        res = super()._action_confirm()
        for order in self:
            company = order.company_id
            website_limit = company.ecom_dynamic_website_id
            if order.website_id and (not website_limit or order.website_id == website_limit):
                locations = company.ecom_dynamic_source_location_ids
                strategy = company.ecom_dynamic_strategy
                pickings = order.picking_ids.filtered(lambda p: p.picking_type_code == 'outgoing')

                if strategy in ('first_available', 'most_available') and locations:
                    for picking in pickings:
                        chosen_loc = None

                        if strategy == 'first_available':
                            for loc in locations:
                                if all(self._get_available_qty(m.product_id, loc) >= m.product_uom_qty
                                       for m in picking.move_ids_without_package):
                                    chosen_loc = loc
                                    break
                        elif strategy == 'most_available':
                            scores = [(loc, self._score_location_for_picking(picking, loc)) for loc in locations]
                            if scores:
                                chosen_loc = max(scores, key=lambda x: x[1])[0]

                        if chosen_loc:
                            fully_covers = all(self._get_available_qty(m.product_id, chosen_loc) >= m.product_uom_qty
                                               for m in picking.move_ids_without_package)
                            if not fully_covers:
                                self._create_internal_transfer(chosen_loc, picking.move_ids_without_package)
                            self._apply_source_location(picking, chosen_loc, strategy)
        return res

    def _create_internal_transfer(self, dest_location, moves):
        StockPicking = self.env['stock.picking']
        StockPickingType = self.env['stock.picking.type']
        for move in moves:
            quant = self.env['stock.quant'].search([
                ('product_id', '=', move.product_id.id),
                ('quantity', '>=', move.product_uom_qty)
            ], limit=1)
            source_loc = quant.location_id
            if not source_loc or source_loc == dest_location:
                continue
            picking_type = StockPickingType.search([
                ('code', '=', 'internal'),
                ('default_location_src_id', '=', source_loc.id),
                ('default_location_dest_id', '=', dest_location.id)
            ], limit=1)
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
