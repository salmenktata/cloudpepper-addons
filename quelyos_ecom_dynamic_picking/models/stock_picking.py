# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # --------- Helpers quantités par base de stock ---------
    def _qy_get_qty_by_basis(self, product, location, basis):
        """Retourne une quantité numérique selon la base choisie."""
        Quant = self.env['stock.quant']
        if basis == "free":
            # quantité libre (réservable) stricte sur l'emplacement
            return Quant._get_available_quantity(product, location, strict=True)
        elif basis == "onhand":
            # physique (quantity) stricte sur l'emplacement
            quants = Quant.search([('product_id', '=', product.id), ('location_id', '=', location.id)])
            return sum(quants.mapped('quantity'))
        else:  # forecast
            # prévisionnel: via le context location → virtual_available
            return product.with_context(location=location.id).virtual_available

    def _qy_parse_strict_order(self, company, locations):
        """Renvoie la liste ordonnée d'IDs d'emplacements selon l'ordre strict défini, sinon l'ordre courant."""
        if not company.quelyos_dynamic_strict_order_enabled or not company.quelyos_dynamic_strict_shop_order:
            return locations.ids
        name_to_id = {loc.display_name.strip().lower(): loc.id for loc in locations}
        order_names = [x.strip().lower() for x in company.quelyos_dynamic_strict_shop_order.split(">") if x.strip()]
        ordered_ids = []
        for nm in order_names:
            loc_id = name_to_id.get(nm)
            if loc_id and loc_id in locations.ids and loc_id not in ordered_ids:
                ordered_ids.append(loc_id)
        for loc in locations:
            if loc.id not in ordered_ids:
                ordered_ids.append(loc.id)
        return ordered_ids

    def _qy_best_covering_shop(self, product, qty_needed, shops, basis, strict_enabled, ordered_ids):
        """
        Renvoie l'emplacement boutique qui couvre 100%:
         - si strict_enabled=True → première de ordered_ids qui couvre
         - sinon → celle qui a le plus de stock >= qty_needed
        """
        if not shops:
            return False
        if strict_enabled:
            for sid in ordered_ids:
                shop = shops.browse(sid)
                if self._qy_get_qty_by_basis(product, shop, basis) >= qty_needed:
                    return shop
            return False
        # pas strict → sélectionner la meilleure boutique qui couvre
        best = False
        best_qty = -1
        for shop in shops:
            q = self._qy_get_qty_by_basis(product, shop, basis)
            if q >= qty_needed and q > best_qty:
                best = shop
                best_qty = q
        return best

    def _qy_best_partial_location(self, product, central, shops, basis):
        """
        Renvoie (location, qty_available) offrant la meilleure couverture partielle
        parmi [central] + boutiques. Si aucune dispo > 0, renvoie (False, 0).
        """
        candidates = []
        if central:
            candidates.append(central)
        candidates += list(shops)
        best = False
        best_qty = 0
        for loc in candidates:
            q = self._qy_get_qty_by_basis(product, loc, basis)
            if q > best_qty:
                best = loc
                best_qty = q
        return best, best_qty

    def _qy_pick_internal_type(self, company):
        PickingType = self.env['stock.picking.type']
        internal_type = PickingType.search([
            ('code', '=', 'internal'),
            ('warehouse_id.company_id', '=', company.id)
        ], limit=1)
        if not internal_type:
            raise UserError(_("Aucun type de transfert interne trouvé pour la société %s.") % company.display_name)
        return internal_type

    # --------- Stratégie principale ---------
    @api.model
    def quelyos_dynamic_pick(self, picking):
        """Stratégie Quelyos – Dynamic Picking avec priorités 1→4 et réassort partiel depuis le central."""
        company = picking.company_id
        if not company.quelyos_dynamic_enabled or picking.picking_type_code != 'outgoing':
            return

        # Optionnel: limiter aux commandes eCommerce
        if company.quelyos_dynamic_ecom_only and not picking.sale_id.website_id:
            return

        basis = company.quelyos_dynamic_stock_basis or "free"
        central = company.quelyos_dynamic_central_location_id
        shops = company.quelyos_dynamic_locations
        if not shops and not central:
            return

        # Pré-tri des boutiques selon ordre strict éventuel
        ordered_ids = self._qy_parse_strict_order(company, shops)
        shops_ordered = self.env['stock.location'].browse(ordered_ids)

        # Pour chaque move "product"
        move_lines = picking.move_ids_without_package.filtered(lambda m: m.product_id.type == 'product')
        for move in move_lines:
            product = move.product_id
            qty_needed = move.product_uom_qty

            # ----- Priorité 1: Central couvre 100% -----
            if central:
                qty_central = self._qy_get_qty_by_basis(product, central, basis)
                if qty_central >= qty_needed:
                    move.location_id = central.id
                    move.with_context(quelyos_force_exact_location=True)._action_assign()
                    if company.quelyos_dynamic_log_success:
                        picking.message_post(
                            body=_("Quelyos – Dynamic Picking: %s unités assignées depuis %s (central, 100%%).") % (
                                qty_needed, central.display_name
                            )
                        )
                    continue

            # ----- Priorité 2/3: Boutique couvrant 100% -----
            strict = company.quelyos_dynamic_strict_order_enabled
            covering_shop = self._qy_best_covering_shop(
                product=product,
                qty_needed=qty_needed,
                shops=shops,
                basis=basis,
                strict_enabled=strict,
                ordered_ids=ordered_ids
            )
            if covering_shop:
                move.location_id = covering_shop.id
                move.with_context(quelyos_force_exact_location=True)._action_assign()
                if company.quelyos_dynamic_log_success:
                    picking.message_post(
                        body=_("Quelyos – Dynamic Picking: %s unités assignées depuis %s (boutique, 100%%).") % (
                            qty_needed, covering_shop.display_name
                        )
                    )
                continue

            # ----- Priorité 4: Couverture partielle -----
            if company.quelyos_dynamic_partial_enabled:
                best_loc, best_qty = self._qy_best_partial_location(product, central, shops_ordered, basis)
                if best_loc and best_qty > 0:
                    # Assigner la ligne sur la meilleure couverture et réserver ce qui est disponible
                    move.location_id = best_loc.id
                    move.with_context(quelyos_force_exact_location=True)._action_assign()

                    # Si la meilleure couverture n'est pas le central et que du stock manque,
                    # tenter un réassort partiel depuis le central si possible
                    shortfall = max(qty_needed - best_qty, 0)
                    if shortfall > 0 and best_loc != central:
                        if central and company.quelyos_dynamic_auto_confirm_replenishment:
                            internal_type = self._qy_pick_internal_type(company)
                            replenishment = self.env['stock.picking'].create({
                                'picking_type_id': internal_type.id,
                                'location_id': central.id,
                                'location_dest_id': best_loc.id,
                                'company_id': company.id,
                                'origin': _("Réassort (partiel) pour %s") % picking.name,
                                'move_ids_without_package': [(0, 0, {
                                    'name': product.display_name,
                                    'product_id': product.id,
                                    'product_uom': move.product_uom.id,
                                    'product_uom_qty': shortfall,
                                    'location_id': central.id,
                                    'location_dest_id': best_loc.id,
                                    'company_id': company.id,
                                })],
                            })
                            replenishment.action_confirm()
                            replenishment.move_ids_without_package.with_context(quelyos_force_exact_location=True)._action_assign()
                            if company.quelyos_dynamic_auto_validate_replenishment:
                                if all(m.state == 'assigned' and m.reserved_availability >= m.product_uom_qty
                                       for m in replenishment.move_ids_without_package):
                                    replenishment.button_validate()

                            # Re-tenter la réservation de la ligne client depuis la boutique
                            move.with_context(quelyos_force_exact_location=True)._action_assign()

                            picking.message_post(
                                body=_(
                                    "Quelyos – Dynamic Picking: %s/%s unités disponibles depuis %s ; "
                                    "réassort interne de %s depuis %s déclenché."
                                ) % (best_qty, qty_needed, best_loc.display_name, shortfall, central.display_name)
                            )
                        else:
                            # Pas de central ou pas de réassort auto: on réserve ce qu'on peut
                            picking.message_post(
                                body=_(
                                    "Quelyos – Dynamic Picking: %s/%s unités réservées depuis %s (pas de réassort possible)."
                                ) % (best_qty, qty_needed, best_loc.display_name)
                            )
                    else:
                        # Meilleure couverture est le central (partielle) ou 100% déjà réservé par assign
                        if company.quelyos_dynamic_log_success:
                            picking.message_post(
                                body=_(
                                    "Quelyos – Dynamic Picking: couverture partielle %s/%s depuis %s."
                                ) % (best_qty, qty_needed, best_loc.display_name)
                            )
                    continue

            # ----- Aucun choix possible -----
            picking.message_post(
                body=_(
                    "Quelyos – Dynamic Picking: aucune source ne couvre %s unités (et aucune couverture partielle disponible)."
                ) % qty_needed
            )
