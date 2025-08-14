# -*- coding: utf-8 -*-
from collections import defaultdict
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    # Point d’entrée : réservation
    def action_assign(self):
        for picking in self:
            picking._quelyos_apply_strategy_if_needed()
        return super().action_assign()

    # Stratégie complète
    def _quelyos_apply_strategy_if_needed(self):
        """
        Applique la stratégie de choix de source AVANT la réservation :
          - si nécessaire, annule toute réservation existante (unreserve)
          - recible la source des mouvements
          - si source != central : crée réassort interne, auto-confirme/réserve (+ auto-valide si 100% réservé et option activée)
        """
        self.ensure_one()

        # ---- Vérif d'éligibilité + logs 'skip reason'
        ok, reason = self._quelyos_should_run_strategy_with_reason()
        if not ok:
            # journaliser pour diagnostic sur l'instance
            _logger.info("Quelyos DP: SKIP on %s -> %s", self.name, reason)
            try:
                self.message_post(body=_("Quelyos – Dynamic Picking: stratégie ignorée. Raison: <i>%s</i>.") % reason)
            except Exception:
                pass
            return

        ICP = self.env["ir.config_parameter"].sudo()
        basis = (ICP.get_param("quelyos_dynamic_stock_basis") or "free").strip()
        strict_enabled = str(ICP.get_param("quelyos_dynamic_strict_order_enabled") or "False") in ("1", "True", "true")
        strict_order_text = (ICP.get_param("quelyos_dynamic_strict_shop_order") or "").strip()

        central, shops = self._quelyos_get_locations_from_conf()
        if not central and not shops:
            self.message_post(body=_("Quelyos – Dynamic Picking: ignoré (aucune configuration d'emplacements définie)."))
            return

        req = self._quelyos_requirements_per_product()
        if not req:
            self.message_post(body=_("Quelyos – Dynamic Picking: ignoré (aucun besoin net à réserver)."))
            return

        choice, details = self._quelyos_choose_source(req, central, shops, basis, strict_enabled, strict_order_text)
        if not choice:
            self.message_post(body=_("Quelyos – Dynamic Picking: aucune source sélectionnée (détails: %s).") % details)
            return

        # ✅ CORRECTION : libérer toutes les réservations existantes avant de recibler
        moves_to_unreserve = self.move_ids_without_package.filtered(
            lambda m: m.state not in ('cancel',) and (m.reserved_availability or 0.0) > 0.0
        )
        if moves_to_unreserve:
            try:
                moves_to_unreserve._do_unreserve()
            except Exception as e:
                _logger.exception("Unreserve failed on picking %s: %s", self.name, e)
                self.message_post(body=_("Échec libération des réservations existantes : %s") % e)

        # Re-cible la source
        self._quelyos_retarget_moves(choice)

        # Réassort si source != central
        if central and choice.id != central.id:
            missing = self._quelyos_missing_by_product(req, choice, basis)
            if any(qty > 0 for qty in missing.values()):
                repick = self._quelyos_create_internal_replenishment(central, choice, missing)
                if repick:
                    auto_confirm = str(ICP.get_param("quelyos_dynamic_auto_confirm_replenishment") or "True") in ("1", "True", "true")
                    auto_validate = str(ICP.get_param("quelyos_dynamic_auto_validate_replenishment") or "True") in ("1", "True", "true")
                    if auto_confirm:
                        try:
                            repick.action_confirm()
                            repick.action_assign()
                            # Option : auto-valider si 100% réservé
                            if auto_validate and self._quelyos_is_fully_reserved(repick):
                                if hasattr(repick, "action_set_quantities_to_reservation"):
                                    repick.action_set_quantities_to_reservation()
                                repick.button_validate()
                        except Exception as e:
                            _logger.exception("Auto-confirm/assign/validate failed on replenishment %s: %s", repick.name, e)
                            repick.message_post(body=_("Échec auto (confirm/réservation/validation) : %s") % e)

                    # Journalise sur le picking d’origine
                    msg = _(
                        "Réassort interne créé : <b>%s</b> (de %s vers %s). "
                        "Produits/Qtés manquants : %s"
                    ) % (
                        repick.name,
                        central.display_name,
                        choice.display_name,
                        ", ".join(
                            "%s: %s" % (self.env["product.product"].browse(pid).display_name, qty)
                            for pid, qty in missing.items() if qty > 0
                        )
                    )
                    self.message_post(body=msg)

        # Log stratégie
        self.message_post(body=_("Quelyos – Dynamic Picking: Source retenue = <b>%s</b>. Détails: %s") %
                               (choice.display_name, details))

    # Helper : fully reserved ?
    def _quelyos_is_fully_reserved(self, picking):
        """Vrai si toutes les lignes sont entièrement réservées (en UoM des mouvements)."""
        for mv in picking.move_ids_without_package.filtered(lambda m: m.state not in ("cancel",)):
            rounding = mv.product_uom.rounding or 1e-6
            if (mv.product_uom_qty - (mv.reserved_availability or 0.0)) > rounding:
                return False
        return True

    # Conditions d’exécution (avec raison textuelle pour logs)
    def _quelyos_should_run_strategy_with_reason(self):
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()

        enabled = str(ICP.get_param("quelyos_dynamic_enabled") or "False") in ("1", "True", "true")
        if not enabled:
            return False, _("stratégie désactivée dans Paramètres > Ventes")

        if self.picking_type_id.code != "outgoing":
            return False, _("picking non-sortant (code != 'outgoing')")

        ecom_only = str(ICP.get_param("quelyos_dynamic_ecom_only") or "False") in ("1", "True", "true")
        if ecom_only:
            so = self.sale_id
            if not so or not hasattr(so, "website_id") or not so.website_id:
                return False, _("option 'Limiter aux commandes eCommerce' activée et ce picking ne provient pas d'une commande web")
        return True, ""

    # Lecture conf locations
    def _quelyos_get_locations_from_conf(self):
        ICP = self.env["ir.config_parameter"].sudo()
        central_id = int(ICP.get_param("quelyos_dynamic_central_location_id", default="0") or 0)
        shops = (ICP.get_param("quelyos_dynamic_shop_ids", default="") or "").strip()
        shop_ids = []
        if shops:
            try:
                shop_ids = [int(x) for x in shops.split(",") if x.strip().isdigit()]
            except Exception:
                shop_ids = []
        central = self.env["stock.location"].browse(central_id) if central_id else False
        shops_rs = self.env["stock.location"].browse(shop_ids) if shop_ids else self.env["stock.location"]
        return central if central and central.exists() else False, shops_rs.filtered(lambda l: l.exists())

    # Besoins nets (en UoM produit)
    def _quelyos_requirements_per_product(self):
        req = defaultdict(float)
        for mv in self.move_ids_without_package.filtered(lambda m: m.state not in ("cancel",) and m.product_id and m.product_id.type in ("product",)):
            need_in_move_uom = max(0.0, mv.product_uom_qty - (mv.reserved_availability or 0.0))
            if not need_in_move_uom:
                continue
            qty_in_product_uom = mv.product_uom._compute_quantity(need_in_move_uom, mv.product_id.uom_id, rounding_method="HALF-UP")
            req[mv.product_id.id] += qty_in_product_uom
        return dict(req)

    # Dispo par base
    def _quelyos_available_qty(self, product, location, basis):
        p = product.with_context(location=location.id)
        if basis == "onhand":
            return p.qty_available
        elif basis == "forecast":
            return p.virtual_available
        return getattr(p, "free_qty", p.qty_available - p.outgoing_qty)

    # Choix de la source (P1→P4)
    def _quelyos_choose_source(self, req, central, shops, basis, strict_enabled, strict_order_text):
        details = []

        def covers_all(location):
            for pid, need in req.items():
                have = self._quelyos_available_qty(self.env["product.product"].browse(pid), location, basis)
                if have + 1e-6 < need:
                    return False
            return True

        def coverage_score(location):
            free_sum = 0.0
            cover_sum = 0.0
            for pid, need in req.items():
                prod = self.env["product.product"].browse(pid)
                have = self._quelyos_available_qty(prod, location, basis)
                free_sum += max(0.0, have)
                cover_sum += max(0.0, min(have, need))
            return cover_sum, free_sum

        # P1: Central couvre tout
        if central:
            if covers_all(central):
                details.append(_("P1: Central couvre tout → %s") % central.display_name)
                return central, "; ".join(details)
            else:
                cov = coverage_score(central)
                details.append(_("P1: Central ne couvre pas tout (cover=%s, free=%s)") % (cov[0], cov[1]))

        # P2: Ordre strict
        shops_list = shops
        if strict_enabled and strict_order_text:
            order_names = [x.strip() for x in strict_order_text.split(">") if x.strip()]
            def order_key(loc):
                for i, name in enumerate(order_names):
                    if name.lower() in (loc.display_name or "").lower():
                        return i
                return len(order_names) + 1
            shops_list = shops.sorted(key=order_key)

        if strict_enabled:
            for loc in shops_list:
                if covers_all(loc):
                    details.append(_("P2: Ordre strict ON → %s couvre tout") % loc.display_name)
                    return loc, "; ".join(details)
            details.append(_("P2: Aucune boutique de l'ordre strict ne couvre tout"))

        # P3: Sans ordre strict → meilleure boutique qui couvre tout
        if not strict_enabled and shops:
            candidates = []
            for loc in shops:
                if covers_all(loc):
                    cov = coverage_score(loc)
                    candidates.append((cov[0], cov[1], loc))
            if candidates:
                candidates.sort(reverse=True)
                best = candidates[0][2]
                details.append(_("P3: Meilleure boutique (sans ordre strict) couvrant tout → %s") % best.display_name)
                return best, "; ".join(details)
            details.append(_("P3: Aucune boutique ne couvre tout"))

        # P4: Meilleure couverture globale (central vs boutiques)
        candidates = []
        if central:
            cov = coverage_score(central)
            candidates.append((cov[0], cov[1], central))
        for loc in shops:
            cov = coverage_score(loc)
            candidates.append((cov[0], cov[1], loc))
        candidates.sort(reverse=True)
        chosen = candidates[0][2] if candidates else False
        if chosen:
            details.append(_("P4: Personne ne couvre 100%% → meilleure couverture globale → %s") % chosen.display_name)
        return chosen, "; ".join(details)

    # Appliquer la source choisie
    def _quelyos_retarget_moves(self, new_source_location):
        for mv in self.move_ids_without_package.filtered(lambda m: m.state not in ("cancel",)):
            if mv.location_id.id != new_source_location.id:
                mv.location_id = new_source_location.id
                # NOTE: la réservation réelle sera refaite par super().action_assign()

    # Quantités manquantes (à réassortir)
    def _quelyos_missing_by_product(self, req, chosen_location, basis):
        missing = {}
        for pid, need in req.items():
            prod = self.env["product.product"].browse(pid)
            have = max(0.0, self._quelyos_available_qty(prod, chosen_location, basis))
            missing[pid] = max(0.0, need - have)
        return missing

    # Création du picking interne
    def _quelyos_create_internal_replenishment(self, central, dest_location, missing_dict):
        moves_vals = []
        for pid, qty in missing_dict.items():
            if qty <= 0:
                continue
            prod = self.env["product.product"].browse(pid)
            moves_vals.append((0, 0, {
                "name": _("Réassort %s") % (prod.display_name,),
                "product_id": prod.id,
                "product_uom": prod.uom_id.id,
                "product_uom_qty": qty,
                "location_id": central.id,
                "location_dest_id": dest_location.id,
            }))
        if not moves_vals:
            return False

        ptype = self.env["stock.picking.type"].search(
            [("code", "=", "internal"), ("company_id", "=", self.company_id.id)], limit=1
        ) or self.env["stock.picking.type"].search([("code", "=", "internal")], limit=1)
        if not ptype:
            raise UserError(_("Aucun type de picking interne trouvé (code 'internal')."))

        repick = self.env["stock.picking"].create({
            "picking_type_id": ptype.id,
            "company_id": self.company_id.id,
            "origin": _("Réassort pour %s") % (self.name,),
            "location_id": central.id,
            "location_dest_id": dest_location.id,
            "move_ids_without_package": moves_vals,
            "note": _("Créé automatiquement par Quelyos – Dynamic Picking."),
        })
        _logger.info("Réassort interne créé %s pour %s", repick.name, self.name)
        repick.message_post(body=_("Réassort créé automatiquement pour <b>%s</b>.") % self.name)
        return repick
