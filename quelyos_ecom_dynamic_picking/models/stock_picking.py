# -*- coding: utf-8 -*-
from collections import defaultdict
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    # --- Hooks/Entry point ---
    def action_assign(self):
        """
        Au moment de la réservation, on applique la stratégie :
        - choisir la meilleure source (central/boutiques)
        - si source != central : créer un réassort interne central -> source pour le manque
        - auto-confirmer et tenter la réservation du réassort si l'option est activée
        - mettre à jour les moves (location_id) avec la source décidée
        """
        for picking in self:
            picking._quelyos_apply_strategy_if_needed()
        return super().action_assign()

    # --- Core Strategy ---
    def _quelyos_apply_strategy_if_needed(self):
        self.ensure_one()
        if not self._quelyos_should_run_strategy():
            return

        ICP = self.env["ir.config_parameter"].sudo()
        basis = (ICP.get_param("quelyos_dynamic_stock_basis") or "free").strip()
        strict_enabled = str(ICP.get_param("quelyos_dynamic_strict_order_enabled") or "False") in ("1", "True", "true")
        strict_order_text = (ICP.get_param("quelyos_dynamic_strict_shop_order") or "").strip()

        central, shops = self._quelyos_get_locations_from_conf()
        if not central and not shops:
            return  # pas de configuration utile

        # Besoins de la commande
        req = self._quelyos_requirements_per_product()

        if not req:
            return

        # Évalue quantités dispos + choix
        choice, details = self._quelyos_choose_source(req, central, shops, basis, strict_enabled, strict_order_text)

        # Si rien trouvé (cas extrême), on laisse la config initiale
        if not choice:
            return

        # Applique la source aux mouvements
        self._quelyos_retarget_moves(choice)

        # Si source != central → réassort central -> source
        if central and choice.id != central.id:
            missing = self._quelyos_missing_by_product(req, choice, basis)
            if any(qty > 0 for qty in missing.values()):
                repick = self._quelyos_create_internal_replenishment(central, choice, missing)
                if repick:
                    # Auto-confirm + reserve si option active
                    auto = str(ICP.get_param("quelyos_dynamic_auto_confirm_replenishment") or "True") in ("1", "True", "true")
                    if auto:
                        try:
                            repick.action_confirm()
                            repick.action_assign()
                        except Exception as e:
                            _logger.exception("Auto-confirm/assign failed on replenishment %s: %s", repick.name, e)
                            repick.message_post(body=_("Échec de l'auto-confirmation/réservation : %s") % e)

                    # Log sur le picking d'origine
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

        # Trace côté picking
        log = _(
            "Qelyos – Dynamic Picking: Source retenue = <b>%s</b>. Détails: %s"
        ) % (
            choice.display_name,
            details,
        )
        self.message_post(body=log)

    # --- Strategy helpers ---
    def _quelyos_should_run_strategy(self):
        """ Vérifie si on doit appliquer la stratégie pour CE picking. """
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        enabled = str(ICP.get_param("quelyos_dynamic_enabled") or "False") in ("1", "True", "true")
        if not enabled:
            return False

        # Sortants uniquement
        if self.picking_type_id.code != "outgoing":
            return False

        # eCommerce only ?
        ecom_only = str(ICP.get_param("quelyos_dynamic_ecom_only") or "False") in ("1", "True", "true")
        if ecom_only:
            so = self.sale_id
            # eCom s'il y a un website sur la commande. On ne dépend PAS de website_sale (sécurisé).
            if not so or not hasattr(so, "website_id") or not so.website_id:
                return False
        return True

    def _quelyos_get_locations_from_conf(self):
        """ Renvoie (central_location, shops_recordset) """
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
        """ Besoins nets en UoM produit (réservations déduites). """
        req = defaultdict(float)
        for mv in self.move_ids_without_package.filtered(lambda m: m.state not in ("cancel",) and m.product_id and m.product_id.type in ("product",)):
            # Besoin net = demandé - déjà réservé
            need_in_move_uom = max(0.0, mv.product_uom_qty - (mv.reserved_availability or 0.0))
            if not need_in_move_uom:
                continue
            # Convertir vers l'UoM du produit si besoin
            qty_in_product_uom = mv.product_uom._compute_quantity(need_in_move_uom, mv.product_id.uom_id, rounding_method="HALF-UP")
            req[mv.product_id.id] += qty_in_product_uom
        return dict(req)

    def _quelyos_available_qty(self, product, location, basis):
        """ Quantité dispo à un emplacement selon la base choisie. """
        p = product.with_context(location=location.id)
        if basis == "onhand":
            return p.qty_available
        elif basis == "forecast":
            return p.virtual_available
        # default: free
        # Certains Odoo exposent 'free_qty'
        return getattr(p, "free_qty", p.qty_available - p.outgoing_qty)

    def _quelyos_choose_source(self, req, central, shops, basis, strict_enabled, strict_order_text):
        """
        Implémente les 4 priorités :
          1) Central couvre tout → central
          2) Strict ON : 1ère boutique de la liste qui couvre tout
          3) Strict OFF : meilleure boutique (si elle couvre tout)
          4) Sinon : emplacement (central ou boutique) avec meilleure couverture globale
        Renvoie (record location choisi | False, details string)
        """
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

        # P1: Central couvre tout ?
        if central:
            if covers_all(central):
                details.append(_("P1: Central couvre tout → %s") % central.display_name)
                return central, "; ".join(details)
            else:
                cov = coverage_score(central)
                details.append(_("P1: Central ne couvre pas tout (cover=%s, free=%s)") % (cov[0], cov[1]))

        # Prépare liste boutiques
        shops_list = shops
        # P2: Ordre strict -> parser texte et réordonner
        if strict_enabled and strict_order_text:
            order_names = [x.strip() for x in strict_order_text.split(">") if x.strip()]
            def order_key(loc):
                # score élevé si nom présent tôt dans l'ordre
                for i, name in enumerate(order_names):
                    if name.lower() in (loc.display_name or "").lower():
                        return i
                # si pas dans la liste -> après
                return len(order_names) + 1
            shops_list = shops.sorted(key=order_key)

        # P2: strict ON → 1ère boutique qui couvre tout
        if strict_enabled:
            for loc in shops_list:
                if covers_all(loc):
                    details.append(_("P2: Ordre strict ON → %s couvre tout") % loc.display_name)
                    return loc, "; ".join(details)
            details.append(_("P2: Aucune boutique de l'ordre strict ne couvre tout"))

        # P3: strict OFF → meilleure boutique si elle couvre tout (tie-break: free_sum)
        if not strict_enabled and shops:
            candidates = []
            for loc in shops:
                if covers_all(loc):
                    cov = coverage_score(loc)
                    candidates.append((cov[0], cov[1], loc))
            if candidates:
                candidates.sort(reverse=True)  # max(cover_sum, free_sum)
                best = candidates[0][2]
                details.append(_("P3: Meilleure boutique (sans ordre strict) couvrant tout → %s") % best.display_name)
                return best, "; ".join(details)
            details.append(_("P3: Aucune boutique ne couvre tout"))

        # P4: Personne ne couvre tout → meilleur taux de couverture global central vs boutiques
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
            details.append(_("P4: Personne ne couvre 100%% → choix de la meilleure couverture globale → %s") % chosen.display_name)
        return chosen, "; ".join(details)

    def _quelyos_retarget_moves(self, new_source_location):
        """ Remplace la source de tous les moves par l'emplacement choisi. """
        for mv in self.move_ids_without_package.filtered(lambda m: m.state not in ("cancel",)):
            if mv.location_id.id != new_source_location.id:
                mv.location_id = new_source_location.id

    def _quelyos_missing_by_product(self, req, chosen_location, basis):
        """ Calcule les quantités manquantes (en UoM produit) à transférer depuis le central. """
        missing = {}
        for pid, need in req.items():
            prod = self.env["product.product"].browse(pid)
            have = max(0.0, self._quelyos_available_qty(prod, chosen_location, basis))
            miss = max(0.0, need - have)
            missing[pid] = miss
        return missing

    def _quelyos_create_internal_replenishment(self, central, dest_location, missing_dict):
        """ Crée un picking interne central -> dest pour les quantités manquantes. """
        # Filtrer les lignes utiles
        moves_vals = []
        for pid, qty in missing_dict.items():
            if qty <= 0:
                continue
            prod = self.env["product.product"].browse(pid)
            moves_vals.append((
                0, 0, {
                    "name": _("Réassort %s") % (prod.display_name,),
                    "product_id": prod.id,
                    "product_uom": prod.uom_id.id,
                    "product_uom_qty": qty,
                    "location_id": central.id,
                    "location_dest_id": dest_location.id,
                }
            ))
        if not moves_vals:
            return False

        # Type de transfert interne (code='internal')
        ptype = self.env["stock.picking.type"].search(
            [("code", "=", "internal"), ("company_id", "=", self.company_id.id)], limit=1
        )
        if not ptype:
            ptype = self.env["stock.picking.type"].search([("code", "=", "internal")], limit=1)
        if not ptype:
            raise UserError(_("Aucun type de picking interne trouvé (code 'internal')."))

        vals = {
            "picking_type_id": ptype.id,
            "company_id": self.company_id.id,
            "origin": _("Réassort pour %s") % (self.name,),
            "location_id": central.id,
            "location_dest_id": dest_location.id,
            "move_ids_without_package": moves_vals,
            "note": _("Créé automatiquement par Quelyos – Dynamic Picking."),
        }
        repick = self.env["stock.picking"].create(vals)
        _logger.info("Réassort interne créé %s pour %s", repick.name, self.name)
        repick.message_post(body=_("Réassort créé automatiquement pour <b>%s</b>.") % self.name)
        return repick
