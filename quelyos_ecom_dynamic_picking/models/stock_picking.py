# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    # ---------------------------------------------------------------------
    # Logs utilitaires
    # ---------------------------------------------------------------------
    def _quelyos_log_event(self, kind, payload=None):
        payload = payload or {}
        try:
            self.message_post(body=_("QELYOS/%s: %s") % (kind, payload))
        except Exception:
            pass

    # ---------------------------------------------------------------------
    # Paramètres (ir.config_parameter, conserve ta logique actuelle)
    # ---------------------------------------------------------------------
    def _qconf_get(self, key, default=None):
        ICP = self.env["ir.config_parameter"].sudo()
        v = ICP.get_param(f"quelyos_dynamic_{key}")
        if v in (None, "", False):
            v = ICP.get_param(f"quelyos_ecom_dynamic_picking.{key}")
        return v if v not in (None, "") else default

    # ---------------------------------------------------------------------
    # Helpers stock selon la base (free / onhand / forecast)
    # ---------------------------------------------------------------------
    def _qy_available_qty(self, product, location, basis):
        if not location:
            return 0.0
        if basis == "free":
            quants = self.env["stock.quant"].sudo().read_group(
                domain=[("product_id", "=", product.id), ("location_id", "child_of", location.id)],
                fields=["quantity:sum", "reserved_quantity:sum"],
                groupby=["product_id"],
            )
            qty = (quants and quants[0].get("quantity", 0.0)) or 0.0
            res = (quants and quants[0].get("reserved_quantity", 0.0)) or 0.0
            return max(0.0, qty - res)
        prod_ctx = product.with_context(location=location.id, compute_child=True)
        if basis == "onhand":
            return prod_ctx.qty_available
        if basis == "forecast":
            return prod_ctx.virtual_available
        return 0.0

    # Réservation strictement sur move.location_id
    def _qy_assign_move_exact(self, move):
        move.with_context(quelyos_force_exact_location=True)._action_assign()

    # ---------------------------------------------------------------------
    # Ordre strict by names → liste d'IDs ordonnée
    # ---------------------------------------------------------------------
    def _qy_order_shop_ids(self, shops, order_names_csv):
        if not order_names_csv:
            return shops.ids
        priority_names = [n.strip() for n in order_names_csv.replace(">", ",").split(",") if n.strip()]
        name_to_id = {}
        for loc in shops:
            name_to_id.setdefault((loc.name or "").strip().lower(), loc.id)
            name_to_id.setdefault((loc.display_name or "").strip().lower(), loc.id)
        ordered = []
        for nm in priority_names:
            lid = name_to_id.get(nm.lower())
            if lid and lid in shops.ids and lid not in ordered:
                ordered.append(lid)
        for loc in shops:
            if loc.id not in ordered:
                ordered.append(loc.id)
        return ordered

    # ---------------------------------------------------------------------
    # Boutique couvrant 100% (ordre strict sinon meilleure boutique)
    # ---------------------------------------------------------------------
    def _qy_find_covering_shop(self, product, qty_needed, shops, basis, strict_enabled, ordered_ids):
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
                if (free_q > best_free) or (free_q == best_free and qty_needed > best_cover):
                    best = shop
                    best_free = free_q
                    best_cover = qty_needed
        return best

    # ---------------------------------------------------------------------
    # Meilleure couverture partielle (central + shops)
    # ---------------------------------------------------------------------
    def _qy_best_partial_location(self, product, central, shops, basis):
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
    # Type de picking interne
    # ---------------------------------------------------------------------
    def _qy_get_internal_type(self, company):
        PickingType = self.env["stock.picking.type"]
        internal = PickingType.search(
            [("code", "=", "internal"), ("warehouse_id.company_id", "=", company.id)], limit=1
        )
        if not internal:
            internal = PickingType.search([("code", "=", "internal")], limit=1)
        if not internal:
            raise UserError(_("Aucun type de transfert interne ('internal') disponible pour %s.") % company.display_name)
        return internal

    # ---------------------------------------------------------------------
    # Stratégie principale (appelée automatiquement au confirm de SO)
    # ---------------------------------------------------------------------
    def _quelyos_apply_auto_source_strategy(self):
        for picking in self:
            # APRÈS — traiter aussi les flux 2 étapes (pick) et certains internes
            code = picking.picking_type_id and picking.picking_type_id.code or ""
            if code not in ("pick", "internal", "outgoing"):
                continue

            strategy = self._qconf_get("strategy", "custom")
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
            ordered_ids = self._qy_order_shop_ids(shops, order_names) if strict_enabled else shops.ids
            shops_ordered = self.env["stock.location"].browse(ordered_ids)

            created_replenish = False
            coverage_score = {}

            # ---- Parcours des lignes produit ----
            for move in picking.move_ids_without_package.filtered(lambda m: m.product_id.type == "product"):
                product = move.product_id
                qty_needed = move.product_uom_qty

                # P1: central 100%
                if central:
                    q_central = self._qy_available_qty(product, central, basis)
                    if q_central >= qty_needed:
                        move.location_id = central.id
                        self._qy_assign_move_exact(move)
                        picking.message_post(
                            body=_("📦 Quelyos: %s unités assignées depuis %s (central, 100%%).")
                            % (qty_needed, central.display_name)
                        )
                        continue

                # P2/P3: boutique 100%
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
                    self._qy_assign_move_exact(move)
                    picking.message_post(
                        body=_("📦 Quelyos: %s unités assignées depuis %s (boutique, 100%%).")
                        % (qty_needed, shop_100.display_name)
                    )
                    continue

                # P4: meilleure couverture partielle
                best_loc, best_qty = self._qy_best_partial_location(product, central, shops_ordered, basis)
                coverage_score[product.id] = {"best_loc": best_loc and best_loc.display_name or False, "best_qty": best_qty}
                if best_loc and best_qty > 0.0:
                    move.location_id = best_loc.id
                    self._qy_assign_move_exact(move)  # réserver ce qui est dispo exactement ici

                    manque = max(qty_needed - best_qty, 0.0)
                    if manque > 0.0 and best_loc != central and central:
                        try:
                            internal_type = self._qy_get_internal_type(picking.company_id)
                            rep = self.env["stock.picking"].sudo().create({
                                "picking_type_id": internal_type.id,
                                "location_id": central.id,
                                "location_dest_id": best_loc.id,
                                "company_id": picking.company_id.id,
                                "origin": (picking.name or picking.origin or "") + " / Réassort auto",
                                "move_ids_without_package": [(0, 0, {
                                    "name": product.display_name,
                                    "product_id": product.id,
                                    "product_uom": move.product_uom.id,
                                    "product_uom_qty": manque,
                                    "location_id": central.id,
                                    "location_dest_id": best_loc.id,
                                    "company_id": picking.company_id.id,
                                })],
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

                            # re-tenter l'assign de la ligne client, toujours en exact
                            self._qy_assign_move_exact(move)

                            picking.message_post(
                                body=_("📦 Quelyos: partiel %s/%s depuis %s ; réassort interne de %s depuis %s.")
                                % (best_qty, qty_needed, best_loc.display_name, manque, central.display_name)
                            )
                        except Exception as e:
                            self._quelyos_log_event("replenish_error", {"exp": "Erreur réassort partiel", "erreur": str(e)})
                    else:
                        picking.message_post(
                            body=_("📦 Quelyos: couverture partielle %s/%s depuis %s.")
                            % (best_qty, qty_needed, best_loc and best_loc.display_name or "?")
                        )
                else:
                    picking.message_post(
                        body=_("⚠️ Quelyos: aucune couverture disponible pour %s (demande = %s).")
                        % (product.display_name, qty_needed)
                    )

            # Re-assign global du picking en mode exact (sécurisation finale)
            try:
                picking.with_context(quelyos_force_exact_location=True).action_assign()
            except Exception as e:
                self._quelyos_log_event("assign_error", {"exp": "Erreur réservation client", "erreur": str(e)})

            # Log récap
            self._quelyos_log_event("auto_source", {
                "strategie": strategy,
                "basis": basis,
                "central": central and central.display_name or False,
                "reassort_cree": created_replenish,
                "scores": coverage_score,
            })


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_confirm(self):
        res = super()._action_confirm()
        pickings = self.mapped("picking_ids").filtered(lambda p: p.picking_type_id.code == "outgoing")
        for p in pickings:
            p._quelyos_apply_auto_source_strategy()
        return res
