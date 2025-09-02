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

        # Exemple "Gafsa>Sousse>Soukra": on mappe display_name → id
        # NB: en pratique, on préfère s'appuyer sur des codes techniques. Ici on garde display_name par simplicité UI.
        name_to_id = {loc.display_name.strip().lower(): loc.id for loc in locations}
        order_names = [x.strip().lower() for x in company.quelyos_dynamic_strict_shop_order.split(">") if x.strip()]
        ordered_ids = []
        for nm in order_names:
            loc_id = name_to_id.get(nm)
            if loc_id and loc_id in locations.ids and loc_id not in ordered_ids:
                ordered_ids.append(loc_id)
        # Rajoute les autres non listés à la fin
        for loc in locations:
            if loc.id not in ordered_ids:
                ordered_ids.append(loc.id)
        return ordered_ids

    # --------- Stratégie principale ---------
    @api.model
    def quelyos_dynamic_pick(self, picking):
        """Stratégie Quelyos – Dynamic Picking : choisit une source & éventuellement déclenche un réassort interne."""
        company = picking.company_id
        if not company.quelyos_dynamic_enabled or picking.picking_type_code != 'outgoing':
            return

        # Optionnel: limiter aux commandes eCommerce
        if company.quelyos_dynamic_ecom_only and not picking.sale_id.website_id:
            return

        basis = company.quelyos_dynamic_stock_basis or "free"
        central = company.quelyos_dynamic_central_location_id
        shops = company.quelyos_dynamic_locations
        if not shops:
            return

        # Pré-tri des boutiques selon ordre strict éventuel
        shop_ids_ordered = self._qy_parse_strict_order(company, shops)
        shops_ordered = self.env['stock.location'].browse(shop_ids_ordered)

        # Pour chaque move "product"
        move_lines = picking.move_ids_without_package.filtered(lambda m: m.product_id.type == 'product')
        for move in move_lines:
            product = move.product_id
            qty_needed = move.product_uom_qty

            # 1) Si le central couvre 100% → on cible central directement
            if central:
                qty_central = self._qy_get_qty_by_basis(product, central, basis)
                if qty_central >= qty_needed:
                    move.location_id = central.id

                    # Réservation stricte à l'emplacement exact
                    move.with_context(quelyos_force_exact_location=True)._action_assign()

                    if company.quelyos_dynamic_log_success:
                        picking.message_post(
                            body=_("Quelyos – Dynamic Picking: %s unités assignées depuis %s (central).") % (
                                qty_needed, central.display_name
                            )
                        )
                    continue  # move suivant

            # 2) Sinon, chercher une boutique capable de couvrir 100%
            candidate = False
            for shop in shops_ordered:
                qty_shop = self._qy_get_qty_by_basis(product, shop, basis)
                if qty_shop >= qty_needed:
                    candidate = shop
                    break

            if candidate:
                move.location_id = candidate.id
                move.with_context(quelyos_force_exact_location=True)._action_assign()
                if company.quelyos_dynamic_log_success:
                    picking.message_post(
                        body=_("Quelyos – Dynamic Picking: %s unités assignées depuis %s (boutique).") % (
                            qty_needed, candidate.display_name
                        )
                    )
                continue

            # 3) Si aucune source ne couvre et si réassort auto autorisé → créer un interne central -> boutique
            if central and company.quelyos_dynamic_auto_confirm_replenishment:
                # Choisir la boutique cible: la première (ordre strict) possédant déjà qq stock ou la première tout court
                target_shop = False
                for shop in shops_ordered:
                    if self._qy_get_qty_by_basis(product, shop, basis) > 0:
                        target_shop = shop
                        break
                if not target_shop:
                    target_shop = shops_ordered[:1]

                target_shop = target_shop and (target_shop if isinstance(target_shop, models.BaseModel) else target_shop[0])

                if not target_shop:
                    # Pas de boutique cible trouvée
                    continue

                # Créer un picking interne
                PickingType = self.env['stock.picking.type']
                internal_type = PickingType.search([
                    ('code', '=', 'internal'),
                    ('warehouse_id.company_id', '=', company.id)
                ], limit=1)
                if not internal_type:
                    raise UserError(_("Aucun type de transfert interne trouvé pour la société %s.") % company.display_name)

                replenishment = self.env['stock.picking'].create({
                    'picking_type_id': internal_type.id,
                    'location_id': central.id,
                    'location_dest_id': target_shop.id,
                    'company_id': company.id,
                    'origin': _("Réassort pour %s") % picking.name,
                    'move_ids_without_package': [(0, 0, {
                        'name': product.display_name,
                        'product_id': product.id,
                        'product_uom': move.product_uom.id,
                        'product_uom_qty': qty_needed,
                        'location_id': central.id,
                        'location_dest_id': target_shop.id,
                        'company_id': company.id,
                    })],
                })

                # Confirmer + tenter réservation EXACTE
                replenishment.action_confirm()
                replenishment.move_ids_without_package.with_context(quelyos_force_exact_location=True)._action_assign()

                # Optionnel: auto-valider si 100% réservé
                if company.quelyos_dynamic_auto_validate_replenishment:
                    if all(m.state == 'assigned' and m.reserved_availability >= m.product_uom_qty
                           for m in replenishment.move_ids_without_package):
                        replenishment.button_validate()

                # Informer et enfin affecter la ligne client depuis la boutique cible
                move.location_id = target_shop.id
                move.with_context(quelyos_force_exact_location=True)._action_assign()

                picking.message_post(
                    body=_(
                        "Quelyos – Dynamic Picking: %s unités assignées depuis %s "
                        "(réassort interne créé depuis %s)."
                    ) % (
                        qty_needed,
                        target_shop.display_name,
                        central.display_name,
                    )
                )
            else:
                # Pas de réassort possible → message informatif
                picking.message_post(
                    body=_(
                        "Quelyos – Dynamic Picking: %s unités non disponibles en source unique (pas de réassort possible)."
                    ) % qty_needed
                )
