# -*- coding: utf-8 -*-
from collections import defaultdict
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = "stock.picking"

    def action_assign(self):
        # Appliquer la stratégie avant la réservation standard
        for picking in self:
            picking._quelyos_apply_strategy_if_needed()
        # 👉 Contexte spécial pour forcer un domaine STRICT sur l'emplacement source
        return super(StockPicking, self.with_context(quelyos_force_exact_location=True)).action_assign()

    # -------------------------------------------------------------------------
    #  LOGGING CHATTTER ROBUSTE
    # -------------------------------------------------------------------------
    def _safe_message_post(self, record, body):
        if not record:
            return False
        try:
            subtype = None
            try:
                subtype = self.env.ref("mail.mt_note").id
            except Exception:
                subtype = None
            kw = {"body": body, "message_type": "comment"}
            if subtype:
                kw["subtype_id"] = subtype
            msg = record.sudo().message_post(**kw)
            _logger.info("Quelyos DP: message_post on %s -> mid=%s", record.display_name, getattr(msg, "id", False))
            return getattr(msg, "id", False) or False
        except Exception as e:
            _logger.exception("Quelyos DP: message_post failed on %s: %s", getattr(record, "display_name", record), e)
            return False

    def _post_quelyos_log(self, body):
        self.ensure_one()
        self._safe_message_post(self, body)
        if self.sale_id:
            self._safe_message_post(self.sale_id, body)

    # -------------------------------------------------------------------------
    #  STRATÉGIE
    # -------------------------------------------------------------------------
    def _quelyos_apply_strategy_if_needed(self):
        """
        Applique la stratégie AVANT la réservation:
         1) vérifie l’éligibilité
         2) unreserve existant
         3) calcule besoins
         4) choisit la source (P1→P4) et recible le picking + les moves
         5) crée un réassort central->source si besoin (auto confirm/assign [+ auto validate])
        """
        self.ensure_one()

        ok, reason = self._quelyos_should_run_strategy_with_reason()
        if not ok:
            _logger.info("Quelyos DP: SKIP on %s -> %s", self.name, reason)
            if self.picking_type_id.code == "outgoing":
                self._post_quelyos_log(_("Quelyos – Dynamic Picking: stratégie ignorée. Raison: <i>%s</i>.") % reason)
            return

        ICP = self.env["ir.config_parameter"].sudo()
        basis = (ICP.get_param("quelyos_dynamic_stock_basis") or "free").strip()
        strict_enabled = str(ICP.get_param("quelyos_dynamic_strict_order_enabled") or "False") in ("1", "True", "true")
        strict_order_text = (ICP.get_param("quelyos_dynamic_strict_shop_order") or "").strip()

        central, shops = self._quelyos_get_locations_from_conf()
        if not central and not shops:
            self._post_quelyos_log(_("Quelyos – Dynamic Picking: ignoré (aucune configuration d'emplacements définie)."))
            return

        # (1) Unreserve AVANT de calculer les besoins
        moves_to_unreserve = self.move_ids_without_package.filtered(
            lambda m: m.state not in ('cancel',) and (m.reserved_availability or 0.0) > 0.0
        )
        if moves_to_unreserve:
            try:
                moves_to_unreserve._do_unreserve()
            except Exception as e:
                _logger.exception("Unreserve failed on picking %s: %s", self.name, e)
                self._post_quelyos_log(_("Échec libération des réservations existantes : %s") % e)

        # (2) Besoins nets
        req = self._quelyos_requirements_per_product()
        if not req:
            self._post_quelyos_log(_("Quelyos – Dynamic Picking: ignoré (aucun besoin net à réserver)."))
            return

        # (3) Choix de la source
        choice, details = self._quelyos_choose_source(req, central, shops, basis, strict_enabled, strict_order_text)
        if not choice:
            self._post_quelyos_log(_("Quelyos – Dynamic Picking: aucune source sélectionnée (détails: %s).") % details)
            return

        # (4) Re-cibler le picking, tous les moves ET éventuelles move lines déjà présentes
        self._quelyos_retarget_moves(choice)

        # (5) Réassort central -> source si nécessaire
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
                            if auto_validate and self._quelyos_is_fully_reserved(repick):
                                if hasattr(repick, "action_set_quantities_to_reservation"):
                                    repick.action_set_quantities_to_reservation()
                                repick.button_validate()
                        except Exception as e:
                            _logger.exception("Auto-confirm/assign/validate failed on replenishment %s: %s", repick.name, e)
                            self._safe_message_post(repick, _("Échec auto (confirm/réservation/validation) : %s") % e)

                    msg = _(
                        "Réassort interne créé : <b>%s</b> (de %s vers %s). Produits/Qtés manquants : %s"
                    ) % (
                        repick.name,
                        central.display_name,
                        choice.display_name,
                        ", ".join(
                            "%s: %s" % (self.env['product.product'].browse(pid).display_name, qty)
                            for pid, qty in missing.items() if qty > 0
                        )
                    )
                    self._post_quelyos_log(msg)

        # (6) Log final optionnel
        raw = ICP.get_param("quelyos_dynamic_log_success")
        log_success = False
        if raw is not None:
            s = str(raw).strip().lower()
            log_success = s in ("1", "true", "t", "yes", "y", "on")
        if log_success:
            self._post_quelyos_log(
                _("Quelyos – Dynamic Picking: Source retenue = <b>%s</b>. Détails: %s") %
                (choice.display_name, details)
            )

    # --- Helpers ---

    def _quelyos_is_fully_reserved(self, picking):
        for mv in picking.move_ids_without_package.filtered(lambda m: m.state not in ("cancel",)):
            rounding = mv.product_uom.rounding or 1e-6
            if (mv.product_uom_qty - (mv.reserved_availability or 0.0)) > rounding:
                return False
        return True

    def _quelyos_should_run_strategy_with_reason(self):
    self.ensure_one()
    ICP = self.env["ir.config_parameter"].sudo()

    enabled = str(ICP.get_param("quelyos_dynamic_enabled") or "False") in ("1", "True", "true")
    if not enabled:
        return False, _("stratégie désactivée dans Paramètres > Ventes")

    # ✅ Autoriser la stratégie sur :
    # - les livraisons sortantes (code == 'outgoing')
    # - le picking de 1ʳᵉ étape d'un flux en 2 étapes (type 'internal' avec sequence_code == 'PICK')
    pt = self.picking_type_id
    is_out = (pt.code == "outgoing")
    is_pick_step = (pt.code == "internal" and (pt.sequence_code or "").upper() == "PICK")
    if not (is_out or is_pick_step):
        return False, _("picking non éligible (ni 'outgoing', ni étape PICK interne)")

    ecom_only = str(ICP.get_param("quelyos_dynamic_ecom_only") or "False") in ("1", "True", "true")
    if ecom_only:
        so = self.sale_id
        if not so or not getattr(so, "website_id", False):
            return False, _("option 'Limiter aux commandes eCommerce' activée et ce picking ne provient pas d'une commande web")
    return True, ""


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

    def _quelyos_requirements_per_product(self):
        req = defaultdict(float)
        for mv in self.move_ids_without_package.filtered(lambda m: m.state not in ("cancel",) and m.product_id and m.product_id.type in ("product",)):
            need_in_move_uom = max(0.0, mv.product_uom_qty - (mv.reserved_availability or 0.0))
            if not need_in_move_uom:
                continue
            qty_in_product_uom = mv.product_uom._compute_quantity(need_in_move_uom, mv.product_id.uom_id, rounding_method="HALF-UP")
            req[mv.product_id.id] += qty_in_product_uom
        return dict(req)

    def _quelyos_available_qty(self, product, location, basis):
        p = product.with_context(location=location.id)
        if basis == "onhand":
            return p.qty_available
        elif basis == "forecast":
            return p.virtual_available
        return getattr(p, "free_qty", p.qty_available - p.outgoing_qty)

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

        # P3: Sans ordre strict → meilleure boutique qui couvre tout (tri explicite)
        if not strict_enabled and shops:
            candidates = []
            for loc in shops:
                if covers_all(loc):
                    cov = coverage_score(loc)  # (cover_sum, free_sum)
                    candidates.append((cov[0], cov[1], loc))
            if candidates:
                # Tri clair: 1) couverture (doit = besoin total), 2) stock libre total
                candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
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
        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        chosen = candidates[0][2] if candidates else False
        if chosen:
            details.append(_("P4: Personne ne couvre 100%% → meilleure couverture globale → %s") % chosen.display_name)
        return chosen, "; ".join(details)

    def _quelyos_retarget_moves(self, new_source_location):
        """
        Force l’emplacement source sur:
          - le picking lui-même (location_id)
          - tous les moves (stock.move.location_id)
          - les éventuelles move lines existantes (stock.move.line.location_id)
        """
        # 👉 4.a) P I C K I N G
        if self.location_id.id != new_source_location.id:
            self.location_id = new_source_location.id

        # 👉 4.b) M O V E S
        for mv in self.move_ids_without_package.filtered(lambda m: m.state not in ("cancel",)):
            if mv.location_id.id != new_source_location.id:
                mv.location_id = new_source_location.id

        # 👉 4.c) M O V E  L I N E S  (si déjà créées)
        mls = self.move_line_ids.filtered(lambda ml: ml.state != "cancel")
        if mls:
            try:
                mls.write({"location_id": new_source_location.id})
            except Exception as e:
                _logger.info("Quelyos DP: impossible d'imposer location sur move lines %s: %s", self.name, e)

    def _quelyos_missing_by_product(self, req, chosen_location, basis):
        missing = {}
        for pid, need in req.items():
            prod = self.env["product.product"].browse(pid)
            have = max(0.0, self._quelyos_available_qty(prod, chosen_location, basis))
            missing[pid] = max(0.0, need - have)
        return missing

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

        ptype = self.env["stock.picking_type"].search(
            [("code", "=", "internal"), ("company_id", "=", self.company_id.id)], limit=1
        ) or self.env["stock.picking_type"].search([("code", "=", "internal")], limit=1)
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
        self._safe_message_post(repick, _("Réassort créé automatiquement pour <b>%s</b>.") % self.name)
        return repick
