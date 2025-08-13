# -*- coding: utf-8 -*-
from odoo import models, api, fields
from collections import defaultdict

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # Lien vers les pickings de réassort créés
    quelyos_reassort_picking_ids = fields.Many2many(
        'stock.picking',
        'quelyos_reassort_rel',       # table intermédiaire explicite
        'picking_id',                 # clé source
        'reassort_picking_id',        # clé cible
        string="Pickings de réassort",
        readonly=True
    )

    # ===============================
    # Surcharge de l’assignation auto
    # ===============================
    def action_assign(self):
        res = super().action_assign()
        for picking in self:
            picking._quelyos_apply_auto_source_strategy()
        return res

    # ========================================
    # Application de la stratégie de picking
    # ========================================
    def _quelyos_apply_auto_source_strategy(self):
        ICP = self.env['ir.config_parameter'].sudo()

        strategy = ICP.get_param('quelyos_dynamic_strategy', 'custom')
        stock_basis = ICP.get_param('quelyos_dynamic_stock_basis', 'free')
        only_website = ICP.get_param('quelyos_dynamic_only_website', 'False') == 'True'

        if strategy != 'custom':
            return

        # Critères appliqués dans l’ordre demandé :
        # 1️⃣ Emplacement central
        central_location_id = int(ICP.get_param('quelyos_dynamic_central_location_id', '0'))
        # 2️⃣ Plus grande quantité disponible
        # 3️⃣ Plus grande quantité physique
        # 4️⃣ Magasin avec le plus de lignes déjà présentes dans la commande

        # Récupération des lignes à réserver
        for move in self.move_ids_without_package:
            product = move.product_id
            candidate_locations = self._quelyos_get_candidate_locations(product, stock_basis)

            # Appliquer Critère 1
            chosen_location = None
            if central_location_id and central_location_id in candidate_locations:
                chosen_location = central_location_id

            # Sinon Critère 2
            if not chosen_location:
                chosen_location = self._quelyos_pick_highest_qty(candidate_locations)

            # Sinon Critère 3
            if not chosen_location:
                chosen_location = self._quelyos_pick_highest_onhand(candidate_locations)

            # Sinon Critère 4
            if not chosen_location:
                chosen_location = self._quelyos_pick_most_lines(candidate_locations)

            if chosen_location:
                self._quelyos_reserve_from_location(move, chosen_location)

    # ==========================================
    # Méthodes utilitaires pour la sélection
    # ==========================================
    def _quelyos_get_candidate_locations(self, product, stock_basis):
        """Retourne dict {location_id: qty} en fonction du type de stock choisi."""
        quants = self.env['stock.quant'].read_group(
            [('product_id', '=', product.id),
             ('location_id.usage', '=', 'internal')],
            ['location_id', 'quantity', 'available_quantity'],
            ['location_id']
        )
        result = {}
        for q in quants:
            loc_id = q['location_id'][0]
            if stock_basis == 'free':
                qty = q.get('available_quantity', 0)
            elif stock_basis == 'onhand':
                qty = q.get('quantity', 0)
            else:  # forecast
                qty = product.with_context(location=loc_id).virtual_available
            if qty > 0:
                result[loc_id] = qty
        return result

    def _quelyos_pick_highest_qty(self, candidates):
        """Critère 2 : plus grande quantité disponible."""
        if not candidates:
            return None
        return max(candidates, key=lambda k: candidates[k])

    def _quelyos_pick_highest_onhand(self, candidates):
        """Critère 3 : plus grande quantité physique (On-Hand)."""
        if not candidates:
            return None
        # On recalcule uniquement en On-Hand
        onhand = {}
        for loc_id in candidates:
            qty = self.env['stock.quant'].read_group(
                [('location_id', '=', loc_id),
                 ('product_id', 'in', self.move_ids_without_package.product_id.ids)],
                ['quantity'], ['location_id']
            )[0]['quantity']
            onhand[loc_id] = qty
        if not onhand:
            return None
        return max(onhand, key=lambda k: onhand[k])

    def _quelyos_pick_most_lines(self, candidates):
        """Critère 4 : magasin avec le plus de lignes de la commande."""
        if not candidates:
            return None
        counter = defaultdict(int)
        for move in self.move_ids_without_package:
            for loc_id in candidates:
                counter[loc_id] += 1
        if not counter:
            return None
        return max(counter, key=lambda k: counter[k])

    def _quelyos_reserve_from_location(self, move, location_id):
        """Réserve le mouvement depuis l’emplacement choisi."""
        move.location_id = self.env['stock.location'].browse(location_id)
        move._action_assign()
