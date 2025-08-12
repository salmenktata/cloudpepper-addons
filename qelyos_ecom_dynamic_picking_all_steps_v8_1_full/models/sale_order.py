# -*- coding: utf-8 -*-
from odoo import models, api, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def _get_available_quantities(self, products, locations):
        """
        Récupère les quantités disponibles de tous les produits sur tous les emplacements
        en une seule requête pour optimiser les performances.
        Retourne un dictionnaire de la forme:
        {(product_id, location_id): available_qty}
        """
        quant_model = self.env['stock.quant']
        quants = quant_model.search_read([
            ('product_id', 'in', products.ids),
            ('location_id', 'in', locations.ids),
        ], ['product_id', 'location_id', 'quantity'])

        available_qtys = {}
        for quant in quants:
            key = (quant['product_id'][0], quant['location_id'][0])
            available_qtys[key] = available_qtys.get(key, 0.0) + quant['quantity']
        
        return available_qtys

    def _find_best_location_for_strategy(self, picking, locations, strategy):
        products_to_pick = picking.move_ids_without_package.product_id
        available_qtys = self._get_available_quantities(products_to_pick, locations)

        if strategy == 'first_covering':
            return self._find_best_location_first_covering(picking, locations, available_qtys)
        elif strategy == 'max_dispo':
            return self._find_best_location_max_dispo(picking, locations, available_qtys)
        elif strategy == 'central_then_max_all_then_order':
            return self._find_best_location_central_then_max(picking, locations, available_qtys)
        else: # Toujours dépôt par défaut
            return picking.picking_type_id.default_location_src_id

    def _find_best_location_first_covering(self, picking, locations, available_qtys):
        for location in locations:
            is_covering = True
            for move in picking.move_ids_without_package:
                required_qty = move.product_uom_qty
                key = (move.product_id.id, location.id)
                available_qty = available_qtys.get(key, 0.0)
                if available_qty < required_qty:
                    is_covering = False
                    break
            if is_covering:
                return location
        return None

    def _find_best_location_max_dispo(self, picking, locations, available_qtys):
        best_location = None
        max_total_qty = -1
        for location in locations:
            total_qty_for_location = sum(
                available_qtys.get((move.product_id.id, location.id), 0.0)
                for move in picking.move_ids_without_package
            )
            if total_qty_for_location > max_total_qty:
                max_total_qty = total_qty_for_location
                best_location = location
        return best_location

    def _find_best_location_central_then_max(self, picking, locations, available_qtys):
        central_location = self.company_id.ecom_dynamic_source_location_ids.filtered(lambda l: 'Central' in l.name)
        
        # 1. Tente de couvrir intégralement avec l'emplacement Central
        if central_location:
            is_covering = True
            for move in picking.move_ids_without_package:
                required_qty = move.product_uom_qty
                key = (move.product_id.id, central_location.id)
                available_qty = available_qtys.get(key, 0.0)
                if available_qty < required_qty:
                    is_covering = False
                    break
            if is_covering:
                return central_location
        
        # 2. Cherche l'emplacement avec le max de dispo sur toutes les boutiques
        best_location = self._find_best_location_max_dispo(picking, locations, available_qtys)

        if best_location:
            # Vérifier si cet emplacement couvre la commande
            is_covering = True
            for move in picking.move_ids_without_package:
                required_qty = move.product_uom_qty
                key = (move.product_id.id, best_location.id)
                available_qty = available_qtys.get(key, 0.0)
                if available_qty < required_qty:
                    is_covering = False
                    break
            if is_covering:
                return best_location

        # 3. Si aucun ne couvre, prend le premier emplacement de la liste
        if locations:
            return locations[0]
        
        return None
        
    def _action_confirm(self, *args, **kwargs):
        for order in self:
            if order.picking_ids and order.company_id.ecom_dynamic_strategy != 'default':
                # Récupère le bon de prélèvement qui est le bon de sortie
                picking_to_modify = order.picking_ids.filtered(lambda p: p.picking_type_id.code == 'outgoing')

                if picking_to_modify:
                    locations_to_check = order.company_id.ecom_dynamic_source_location_ids
                    strategy = order.company_id.ecom_dynamic_strategy
                    new_source_location = order._find_best_location_for_strategy(picking_to_modify, locations_to_check, strategy)
                    
                    if new_source_location and new_source_location != picking_to_modify.location_id:
                        picking_to_modify.location_id = new_source_location
                        picking_to_modify.message_post(body=_("Source location automatically set to: %s by dynamic picking strategy: %s.") % (new_source_location.display_name, strategy))
                    elif not new_source_location:
                        picking_to_modify.message_post(body=_("Could not find a suitable source location based on dynamic picking strategy: %s. Default location is used.") % strategy)

        # Appel à la méthode parente après avoir effectué les modifications
        return super(SaleOrder, self)._action_confirm(*args, **kwargs)
