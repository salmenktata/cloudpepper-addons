# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    # ---------------------------------------------------------------------
    # Helpers de log (facultatif mais pratique pour suivre la stratégie)
    # ---------------------------------------------------------------------
    def _quelyos_log_event(self, kind, payload=None):
        """Écrit un message technique structuré dans le chatter (et pourrait être routé vers un logger)."""
        payload = payload or {}
        try:
            self.message_post(body=_("QELYOS/%s: %s") % (kind, payload))
        except Exception:
            # Silencieux si pas de chatter disponible (sécurité)
            pass

    # ---------------------------------------------------------------------
    # Helpers de configuration (via ir.config_parameter, comme ta version actuelle)
    # ---------------------------------------------------------------------
    def _qconf_get(self, key, default=None):
        """Lit un paramètre quelyos depuis ir.config_parameter.

        Priorité aux clés 'quelyos_dynamic_*', fallback sur 'quelyos_ecom_dynamic_picking.*'
        pour compat avec des versions antérieures.
        """
        ICP = self.env["ir.config_parameter"].sudo()
        v = ICP.get_param(f"quelyos_dynamic_{key}")
        if v in (None, "", False):
            v = ICP.get_param(f"quelyos_ecom_dynamic_picking.{key}")
        return v if v not in (None, "") else default

    # ---------------------------------------------------------------------
    # Helpers quantités par base de stock
    # ---------------------------------------------------------------------
    def _qy_available_qty(self, product, location, basis):
        """Retourne la quantité dispo pour product à location selon basis (free / onhand / forecast)."""
        if not location:
            return 0.0

        if basis == "free":
            # Libre = qty - reserved sur l'arborescence (child_of). Simple et robuste côté perfs.
            quants = self.env["stock.quant"].sudo().read_group(
                domain=[("product_id", "=", product.id), ("location_id", "child_of", location.id)],
                fields=["quantity:sum", "reserved_quantity:sum"],
                groupby=["product_id"],
            )
            qty = (quants and quants[0].get("quantity", 0.0)) or 0.0
            res = (quants and quants[0].get("reserved_quantity", 0.0)) or 0.0
            return max(0.0, qty - res)

        # onhand / forecast en contexte de localisation (avec compute_child pour hériter des enfants)
        prod_ctx = product.with_context(location=location.id, compute_child=True)
        if basis == "onhand":
            return prod_ctx.qty_available
        if basis == "forecast":
            return prod_ctx.virtual_available
        return 0.0

    # ---------------------------------------------------------------------
    # Ordre strict (par noms) → renvoie une liste d'IDs dans l'ordre imposé
    # ---------------------------------------------------------------------
    def _qy_order_shop_ids(self, shops, order_names_csv):
        """Mappe une chaîne 'Gafsa>Sousse>Soukra' en ordre d'IDs.

        NB : basé sur 'name' (fragile si renommage/traductions). Idéalement utiliser un code technique dédié.
        """
        if not order_names_csv:
            return shops.ids
        priority_names = [n.strip() for n in order_names_csv.replace(">", ",").split(",") if n.strip()]
        name_to_id = {}
        for loc in shops:
            # on mappe par name et display_name pour un peu plus de tolérance
            name_to_id.setdefault((loc.name or "").strip().lower(), loc.id)
            name_to_id.setdefault((loc.display_name or "").strip().lower(), loc.id)

        ordered = []
        for nm in priority_names:
            loc_id = name_to_id.get(nm.lower())
            if loc_id and loc_id in shops.ids and loc_id not in ordered:
                ordered.append(loc_id)
        # ajoute ceux non listés
        for loc in shops:
            if loc.id not in ordered:
                ordered.append(loc.id)
        return ordered

    # ---------------------------------------------------------------------
    # Trouver la boutique qui couvre 100% (ordre strict OU meilleur score)
    # ---------------------------------------------------------------------
    def _qy_find_covering_shop(self, product, qty_needed, shops, basis, strict_enabled, ordered_ids):
        """Renvoie une boutique couvrant 100%:
         - si strict_enabled=True → première de ordered_ids qui couvre
         - sinon → celle ayant le meilleur score 'libre' (avec tie-break sur couverture) parmi celles qui couvrent 100%.
        """
        if not shops:
            return False

        if strict_enabled:
            for sid in ordered_ids:
                shop = shops.browse(sid)
                if self._qy_available_qty(product, shop, basis) >= qty_needed:
                    return shop
            return False

        best = False
        best_free = -1.0
        best_cover = -1.0
        for shop in shops:
            free_q = self._qy_available_qty(product, shop, basis)
            if free_q >= qty_needed:
                # tie-break : plus de 'free', puis meilleure couverture (ici = qty_needed)
                if (free_q > best_free) or (free_q == best_free and qty_needed > best_cover):
                    best = shop
                    best_free = free_q
                    best_cover = qty_needed
        return best

    # ---------------------------------------------------------------------
    # Meilleure couverture partielle (central + boutiques)
    # ---------------------------------------------------------------------
    def _qy_best_partial_location(self, product, central, shops, basis):
        """Renvoie (location, qty_available) offrant la meilleure couverture partielle parmi [central] + shops."""
        candidates = []
        if central:
            candidates.append(central)
        for s in shops:
            candidates.append(s)

        best = False
        best_qty = 0.0
        for loc in candidates:
            q = self._qy_available_qty(product, loc, basis)
            if q > best_qty:
                best = loc
                best_qty = q
        return best, best_qty

    # ---------------------------------------------------------------------
    # Récupération d'un type de picking interne (sécurisée)
    # ---------------------------------------------------------------------
    def _qy_get_internal_type(self, company):
        PickingType = self.env["stock.picking.type"]
        # priorité : type 'internal' du(s) warehouse de la société
        internal = PickingType.search(
            [("code", "=", "internal"), ("warehouse_id.company_id", "=", company.id)], limit=1
        )
        if not internal:
            # fallback global
            internal = PickingType.search([("code", "=", "internal")], limit=1)
        if not internal:
            raise UserError(_("Aucun type de transfert interne ('internal') disponible pour %s.") % company.display_name)
        return internal

    # ---------------------------------------------------------------------
    # Stratégie principale (appelée automatiquement au confirm de SO, cf. override plus bas)
    # ---------------------------------------------------------------------
    def _quelyos_apply_auto_source_strategy(self):
        """
        Stratégie Quelyos (priorités 1→4) + réassort interne confirmé/assigné/auto-validé:
          1) Central couvre 100% → source = central
          2) Sinon boutique 100% (ordre strict si activé)
          3) Si pas d'ordre strict → meilleure boutique couvrant 100%
          4) Sinon meilleure couverture partielle (central/boutiques). Si source != central, réassort partiel central->source.
        """
        for picking in self:
            # garde-fous
            if not picking.picking_type_id or picking.picking_type_id.code != "outgoing":
                continue

            # -- Paramétrage --
            strategy = self._qconf_get("strategy", "custom")   # conservé pour compat (si tu as d'autres variantes)
            only_web = self._qconf_get("only_website", "False") in ("1", "True", "true")
            basis = self._qconf_get("stock_basis", "free")

            if only_web and not (picking.sale_id and picking.sale_id.website_id):
                continue

            central_id = int(self._qconf_get("central_location_id", 0) or 0)
            shop_ids_csv = self._qconf_get("shop_ids", "") or ""
            shop_ids = [int(x) for x in shop_ids_csv.split(",") if x]

            strict_enabled = self._qconf_get("strict_shop_order_enabled", "False") in ("1", "True", "true")
            order_names = (self._qconf_get("shop_order_names", "") or "")

            central = self.env["stock.location"].browse(central_id) if central_id else False
            shops = self.env["stock.location"].browse(shop_ids)

            # Ordonner les shops si strict
            ordered_ids = self._qy_order_shop_ids(shops, order_names) if strict_enabled else shops.ids
            shops_ordered = self.env["stock.location"].browse(ordered_ids)

            coverage_score = {}  # log/debug
            created_replenish = False
            strategie_appliquee = ""

            # -----------------------
            # Parcours des lignes
            # -----------------------
            product_moves = picking.move_ids_without_package.filtered(lambda m: m.product_id.type == "product")
            for move in product_moves:
                product = move.product_id
                qty_needed = move.product_uom_qty

                # ----- Priorité 1 : central couvre 100% -----
                if central:
                    q_central = self._qy_available_qty(product, central, basis)
                    if q_central >= qty_needed:
                        move.location_id = central.id
                        move.with_context(quelyos_force_exact_location=True)._action_assign()
                        strategie_appliquee = "central_100"
                        if True:  # log optionnel
                            picking.message_post(
                                body=_("📦 Stratégie Quelyos : %s unités assignées depuis %s (central, 100%%).")
                                % (qty_needed, central.display_name)
                            )
                        continue

                # ----- Priorité 2/3 : boutique couvrant 100% -----
                shop_100 = self._qy_find_covering_shop(
                    product=product,
                    qty_needed=qty_needed,
                    shops=shops,
                    basis=basis,
                    strict_enabled=strict_enabled,
                    ordered_ids=ordered_ids,
                )
                if shop_100:
                    move.location_id = shop_100.id
                    move.with_context(quelyos_force_exact_location=True)._action_assign()
                    strategie_appliquee = "shop_100_strict" if strict_enabled else "shop_100_best"
                    if True:
                        picking.message_post(
                            body=_("📦 Stratégie Quelyos : %s unités assignées depuis %s (boutique, 100%%).")
                            % (qty_needed, shop_100.display_name)
                        )
                    continue

                # ----- Priorité 4 : meilleure couverture partielle -----
                best_loc, best_qty = self._qy_best_partial_location(product, central, shops_ordered, basis)
                coverage_score[product.id] = {"best_loc": best_loc and best_loc.display_name or False, "best_qty": best_qty}
                if best_loc and best_qty > 0.0:
                    move.location_id = best_loc.id
                    # réserve tout de suite ce qui est disponible, sur l'emplacement exact
                    move.with_context(quelyos_force_exact_location=True)._action_assign()

                    manque = max(qty_needed - best_qty, 0.0)
                    if manque > 0.0 and best_loc != central:
                        # Tenter un réassort partiel central → best_loc si possible
                        try:
                            internal_type = self._qy_get_internal_type(picking.company_id)
                            moves_data = [{
                                "name": product.display_name,
                                "product_id": product.id,
                                "product_uom": move.product_uom.id,
                                "product_uom_qty": manque,
                                "location_id": central.id if central else False,
                                "location_dest_id": best_loc.id,
                                "company_id": picking.company_id.id,
                            }]
                            rep = self.env["stock.picking"].sudo().create({
                                "picking_type_id": internal_type.id if internal_type else False,
                                "location_id": central.id if central else False,
                                "location_dest_id": best_loc.id,
                                "company_id": picking.company_id.id,
                                "origin": (picking.name or picking.origin or "") + " / Réassort auto",
                                "move_ids_without_package": moves_data,
                            })
                            # Confirm → Assign (exact) → Auto-validate si 100%
                            rep.action_confirm()
                            rep.move_ids_without_package.with_context(quelyos_force_exact_location=True)._action_assign()
                            all_assigned = all(
                                m.state == "assigned" and m.reserved_availability >= m.product_uom_qty
                                for m in rep.move_ids_without_package
                            )
                            if all_assigned:
                                rep.button_validate()
                            created_replenish = True

                            picking.message_post(
                                body=_(
                                    "📦 Stratégie Quelyos : couverture partielle %s/%s depuis %s ; "
                                    "réassort interne de %s depuis %s déclenché."
                                )
                                % (best_qty, qty_needed, best_loc.display_name, manque, central and central.display_name or "?")
                            )
                        except Exception as e:
                            self._quelyos_log_event("replenish_error", {"exp": "Erreur réassort partiel", "erreur": str(e)})
                    else:
                        # Soit c'était le central (partiel) ; soit 100% déjà assigné
                        picking.message_post(
                            body=_("📦 Stratégie Quelyos : couverture partielle %s/%s depuis %s.")
                            % (best_qty, qty_needed, best_loc.display_name)
                        )
                else:
                    # Personne ne couvre même partiellement
                    picking.message_post(
                        body=_("⚠️ Stratégie Quelyos : aucune couverture disponible pour %s (demande = %s).")
                        % (product.display_name, qty_needed)
                    )

            # -----------------------
            # Réserver le picking client (emplacement exact)
            # -----------------------
            try:
                picking.with_context(quelyos_force_exact_location=True).action_assign()
            except Exception as e:
                self._quelyos_log_event("assign_error", {"exp": "Erreur réservation client", "erreur": str(e)})

            # -----------------------
            # Log récapitulatif
            # -----------------------
            self._quelyos_log_event("auto_source", {
                "strategie": strategy,
                "basis": basis,
                "central": central and central.display_name or False,
                "reassort_cree": created_replenish,
                "scores": coverage_score,
            })

    # ---------------------------------------------------------------------
    # Bloqueurs éventuels : exemple de garde-fou (repris de ta version si existant)
    # ---------------------------------------------------------------------
    def _check_blockers_before_validate(self):
        """Exemple de garde-fou éventuel avant validation (facultatif, adapter selon ton flux)."""
        blockers = self.env["stock.picking"].browse()
        # ... tes conditions si besoin ...
        if blockers:
            raise UserError(
                _("Ordre strict : vous devez d'abord terminer '%s' (type : %s).")
                % (blockers.display_name, blockers.picking_type_id.display_name)
            )


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_confirm(self):
        res = super()._action_confirm()
        # Appliquer la stratégie automatiquement aux pickings sortants issus de cette SO
        pickings = self.mapped("picking_ids").filtered(lambda p: p.picking_type_id.code == "outgoing")
        for p in pickings:
            p._quelyos_apply_auto_source_strategy()
        return res
