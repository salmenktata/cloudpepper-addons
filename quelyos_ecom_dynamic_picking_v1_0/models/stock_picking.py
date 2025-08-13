# -*- coding: utf-8 -*-
from odoo import models, fields, api
from collections import defaultdict

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    quelyos_strategy_applied = fields.Char(
        string="Critère appliqué",
        readonly=True
    )
    quelyos_reassort_picking_ids = fields.Many2many(
        'stock.picking',
        string="Pickings de réassort",
        readonly=True
    )

    def action_assign(self):
        """Surcharge de la réservation pour appliquer notre stratégie"""
        for picking in self:
            if picking.picking_type_code != 'outgoing':
                continue
            picking._quelyos_apply_auto_source_strategy()

        return super(StockPicking, self).action_assign()

    def _quelyos_apply_auto_source_strategy(self):
        """Applique la stratégie de sourcing en 4 critères"""
        ICP = self.env['ir.config_parameter'].sudo()
        central_location_id = int(ICP.get_param('quelyos_dynamic_central_location_id', 0))
        shop_ids = ICP.get_param('quelyos_dynamic_shop_ids')
        shop_ids = list(map(int, shop_ids.split(','))) if shop_ids else []

        quelyos_picking_links = []

        for picking in self:
            product_qty_map = defaultdict(float)
            for move in picking.move_ids_without_package:
                product_qty_map[move.product_id.id] += move.product_uom_qty

            # Critère 1 : Réserver depuis l’emplacement central si dispo
            if central_location_id:
                if self._quelyos_reserve_from_location(picking, central_location_id, product_qty_map):
                    picking.quelyos_strategy_applied = "[Critère 1] Réservé depuis l'emplacement central"
                    continue

            # Critère 2 : Réserver depuis le magasin avec le plus de stock dispo
            best_shop_id = self._quelyos_get_shop_with_max_stock(product_qty_map, shop_ids)
            if best_shop_id:
                if self._quelyos_reserve_from_location(picking, best_shop_id, product_qty_map):
                    picking.quelyos_strategy_applied = "[Critère 2] Réservé depuis le magasin avec le plus de stock"
                    continue

            # Critère 3 : Réserver depuis le magasin le plus proche en stock total (sans ordre strict)
            near_shop_id = self._quelyos_get_shop_with_nearest_stock(product_qty_map, shop_ids)
            if near_shop_id:
                if self._quelyos_reserve_from_location(picking, near_shop_id, product_qty_map):
                    picking.quelyos_strategy_applied = "[Critère 3] Réservé depuis le magasin le plus proche en stock"
                    continue

            # Critère 4 : Réassort vers le magasin avec le plus d’articles déjà présents dans la commande
            target_shop_id = self._quelyos_find_shop_for_reassort(product_qty_map, shop_ids)
            if target_shop_id:
                reassort_picking = self._quelyos_create_internal_transfer(central_location_id, target_shop_id, product_qty_map)
                if reassort_picking:
                    quelyos_picking_links.append(reassort_picking.id)
                    picking.quelyos_strategy_applied = "[Critère 4] Réassort créé vers " + reassort_picking.location_dest_id.display_name

            if quelyos_picking_links:
                picking.quelyos_reassort_picking_ids = [(6, 0, quelyos_picking_links)]

    # ===================================================================
    # Méthodes utilitaires
    # ===================================================================
    def _quelyos_reserve_from_location(self, picking, location_id, product_qty_map):
        """Réserve le stock pour un picking depuis un emplacement donné"""
        reserved = False
        for move in picking.move_ids_without_package:
            if move.product_id.id in product_qty_map:
                available_qty = self._quelyos_get_stock_in_location(move.product_id.id, location_id)
                if available_qty >= move.product_uom_qty:
                    move.write({'location_id': location_id})
                    reserved = True
        return reserved

    def _quelyos_get_stock_in_location(self, product_id, location_id):
        """Retourne le stock disponible dans un emplacement"""
        quant = self.env['stock.quant'].search([
            ('product_id', '=', product_id),
            ('location_id', '=', location_id)
        ], limit=1)
        return quant.available_quantity if quant else 0.0

    def _quelyos_get_shop_with_max_stock(self, product_qty_map, shop_ids):
        """Trouve le magasin avec le max de stock pour l’ensemble des produits"""
        max_stock = 0
        best_shop_id = False
        for shop_id in shop_ids:
            total_stock = sum(self._quelyos_get_stock_in_location(pid, shop_id) for pid in product_qty_map)
            if total_stock > max_stock:
                max_stock = total_stock
                best_shop_id = shop_id
        return best_shop_id

    def _quelyos_get_shop_with_nearest_stock(self, product_qty_map, shop_ids):
        """Trouve le magasin avec le stock le plus proche de la demande (mais suffisant)"""
        for shop_id in shop_ids:
            if all(self._quelyos_get_stock_in_location(pid, shop_id) >= qty for pid, qty in product_qty_map.items()):
                return shop_id
        return False

    def _quelyos_find_shop_for_reassort(self, product_qty_map, shop_ids):
        """Trouve le magasin qui possède le plus d’articles déjà dans la commande"""
        best_shop_id = False
        max_matches = 0
        for shop_id in shop_ids:
            matches = sum(1 for pid in product_qty_map if self._quelyos_get_stock_in_location(pid, shop_id) > 0)
            if matches > max_matches:
                max_matches = matches
                best_shop_id = shop_id
        return best_shop_id

    def _quelyos_create_internal_transfer(self, src_location_id, dest_location_id, product_qty_map):
        """Crée un transfert interne pour réassort"""
        if not src_location_id or not dest_location_id:
            return False
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id', '!=', False)
        ], limit=1)
        if not picking_type:
            return False

        picking_vals = {
            'picking_type_id': picking_type.id,
            'location_id': src_location_id,
            'location_dest_id': dest_location_id,
            'move_ids_without_package': [(0, 0, {
                'product_id': pid,
                'name': self.env['product.product'].browse(pid).name,
                'product_uom_qty': qty,
                'product_uom': self.env['product.product'].browse(pid).uom_id.id,
                'location_id': src_location_id,
                'location_dest_id': dest_location_id,
            }) for pid, qty in product_qty_map.items()]
        }
        return self.env['stock.picking'].create(picking_vals)
