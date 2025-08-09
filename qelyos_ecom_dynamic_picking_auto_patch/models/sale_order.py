# -*- coding: utf-8 -*-
from odoo import models, api

class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.model
    def _get_available_qty(self, product, location):
        return self.env['stock.quant']._get_available_quantity(product, location)

    def _action_confirm(self):
        res = super()._action_confirm()
        for order in self:
            company = order.company_id
            website_limit = company.ecom_dynamic_website_id
            if order.website_id and (not website_limit or order.website_id == website_limit):
                locations = company.ecom_dynamic_source_location_ids
                strategy = company.ecom_dynamic_strategy
                pickings = order.picking_ids.filtered(lambda p: p.picking_type_code == "outgoing")

                if strategy == "first_available" and locations:
                    for picking in pickings:
                        chosen_loc = None
                        for loc in locations:
                            if all(self._get_available_qty(m.product_id, loc) >= m.product_uom_qty
                                   for m in picking.move_ids_without_package):
                                chosen_loc = loc
                                break
                        if not chosen_loc and locations:
                            chosen_loc = locations[0]
                            self._create_internal_transfer(chosen_loc, picking.move_ids_without_package)
                        if chosen_loc:
                            # Update picking and all its moves
                            picking.location_id = chosen_loc.id
                            for move in picking.move_ids_without_package:
                                move.location_id = chosen_loc.id
                            # Reassign to refresh reservations
                            picking.action_assign()
                            # Log in chatter
                            picking.message_post(body=f"Source définie sur {chosen_loc.display_name} (stratégie: {strategy})")
        return res

    def _create_internal_transfer(self, dest_location, moves):
        StockPicking = self.env['stock.picking']
        StockPickingType = self.env['stock.picking.type']
        for move in moves:
            source_loc = self.env['stock.quant'].search([
                ('product_id', '=', move.product_id.id),
                ('quantity', '>=', move.product_uom_qty)
            ], limit=1).location_id
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
