# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    quelyos_log = fields.Text(string="Quelyos – Journal (local)")

    # -- Création : log + appliquer stratégie auto si sortie
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._quelyos_log_event("create", {
                "exp": "Création picking",
                "origine": rec.origin,
                "type": rec.picking_type_id and rec.picking_type_id.display_name
            })
        # Appliquer la stratégie uniquement pour les sorties (livraisons)
        for rec in records.filtered(lambda r: r.picking_type_id and r.picking_type_id.code == "outgoing"):
            rec._quelyos_apply_auto_source_strategy()
        return records

    # -- Vérifier dispo (réservation) + log correct pour Odoo 18
    def action_assign(self):
        res = super().action_assign()
        for rec in self:
            # Réservé s’il y a au moins un move en 'assigned' ou 'partially_available'
            reserved_flag = any(m.state in ('assigned', 'partially_available') for m in rec.move_ids_without_package)
            # Quantités réservées sur les move lines (Odoo 18 : 'reserved_qty')
            reserved_qty = sum(rec.move_line_ids.mapped('reserved_qty') or [0.0])
            rec._quelyos_log_event("assign", {
                "exp": "Vérifier la disponibilité",
                "reserved": reserved_flag,
                "reserved_qty": reserved_qty
            })
        return res

    # -- Validation : contrôle ordre strict si activé
    def button_validate(self):
        if self.env["ir.config_parameter"].sudo().get_param("quelyos_ecom_dynamic_picking.strict_order"):
            for picking in self:
                picking._quelyos_check_strict_order_before_validate()
        res = super().button_validate()
        for rec in self:
            rec._quelyos_log_event("validate", {"exp": "Validation picking", "etat": rec.state})
        return res

    # -- Cœur : sélection auto de la source + éventuel réassort CENT -> Boutique
    def _quelyos_apply_auto_source_strategy(self):
        """
        Applique la stratégie de sélection automatique de l’emplacement source.
        exp : 
        - Si CENT/Stock couvre tout → source = CENT
        - Sinon → meilleure boutique (ou ordre strict si activé)
        - Si la boutique ne couvre pas tout → créer un réassort interne CENT → Boutique (manquant)
        """

        P = self.env["ir.config_parameter"].sudo()

        def _qget(key, default=None):
            """
            Helper compatible 2 namespaces :
            - quelyos_dynamic_<key>           (nouvelle vue)
            - quelyos_ecom_dynamic_picking.<key> (ancien namespace)
            """
            v = P.get_param(f"quelyos_dynamic_{key}")
            if v in (None, "", False):
                v = P.get_param(f"quelyos_ecom_dynamic_picking.{key}")
            return v if v not in (None, "") else default

        # Lecture config
        strategy = _qget("strategy", "custom")
        only_web = _qget("only_website", "False") in ("1", "True", "true")
        basis = _qget("stock_basis", "free")

        central_id = int(_qget("central_location_id", 0) or 0)
        shop_ids_csv = _qget("shop_ids", "")
        shop_ids = [int(x) for x in shop_ids_csv.split(",") if x]

        strict_names_enabled = _qget("strict_shop_order_enabled", "False") in ("1", "True", "true")
        order_names = (_qget("shop_order_names", "") or "").replace(">", ",")
        priority_names = [n.strip() for n in order_names.split(",") if n.strip()]

        def available_qty(product, location):
            """
            Quantité dispo par base choisie :
            - free     → product.free_qty au niveau 'location' (+ enfants)
            - onhand   → product.qty_available
            - forecast → product.virtual_available
            """
            if not location:
                return 0.0
            ctx = dict(location=location.id, compute_child=True)
            prod = product.with_context(**ctx)
            if basis == "onhand":
                return prod.qty_available
            elif basis == "forecast":
                return prod.virtual_available
            # défaut : quantité libre
            return getattr(prod, "free_qty", 0.0)

        for picking in self:
            # On cible seulement les livraisons
            if not picking.picking_type_id or picking.picking_type_id.code != "outgoing":
                continue
            if strategy != "custom":
                continue
            if only_web and not getattr(picking, "sale_id", False):
                continue
            if only_web and picking.sale_id and not getattr(picking.sale_id, "website_id", False):
                # Appliquer seulement pour commandes web si option activée
                continue

            Loc = self.env["stock.location"].sudo()
            central = Loc.browse(central_id) if central_id else Loc.browse(False)
            shops = Loc.browse(shop_ids)

            if not (central or shops):
                self._quelyos_log_event("auto_source_skip", {
                    "exp": "Aucun emplacement central ni boutique configuré"
                })
                continue

            # Quantités requises par produit (en UoM du produit)
            req = {}
            for move in picking.move_ids_without_package:
                product = move.product_id
                qty = move.product_uom._compute_quantity(move.product_uom_qty, product.uom_id)
                req[product.id] = req.get(product.id, 0.0) + qty

            # Critère 1 : CENT couvre tout ?
            central_ok = False
            if central:
                central_ok = all(
                    available_qty(self.env["product.product"].browse(pid), central) >= need
                    for pid, need in req.items()
                )

            chosen_shop = False
            coverage_score = {}
            if not central_ok and shops:
                # Critère 3 : ordre strict des boutiques (si activé)
                if strict_names_enabled and priority_names:
                    for name in priority_names:
                        # Match par nom exact (insensible à la casse)
                        shop = shops.filtered(lambda l: l.name.strip().lower() == name.lower())[:1]
                        if shop:
                            ok = all(
                                available_qty(self.env["product.product"].browse(pid), shop)
                                >= need for pid, need in req.items()
                            )
                            if ok:
                                chosen_shop = shop
                                break

                # Sinon, meilleur score (somme des min(dispo, besoin) par produit)
                if not chosen_shop:
                    best_shop = False
                    best_score = -1.0
                    for shop in shops:
                        score = 0.0
                        for pid, need in req.items():
                            have = available_qty(self.env["product.product"].browse(pid), shop)
                            score += max(0.0, min(have, need))
                        coverage_score[shop.id] = score
                        if score > best_score:
                            best_score = score
                            best_shop = shop
                    chosen_shop = best_shop

            # Choix final
            final_source = False
            strategie_appliquee = ""
            if central_ok:
                final_source = central
                strategie_appliquee = "central_complet"
            elif chosen_shop:
                final_source = chosen_shop
                strategie_appliquee = "meilleure_boutique_ou_ordre_strict"
            elif central:
                final_source = central
                strategie_appliquee = "central_par_defaut"
            else:
                final_source = shops[:1] if shops else False
                strategie_appliquee = "premier_disponible"

            if not final_source:
                self._quelyos_log_event("auto_source_fail", {
                    "exp": "Impossible de déterminer une source",
                    "basis": basis
                })
                continue

            # Appliquer la source sur le picking + les moves
            picking.write({"location_id": final_source.id})
            for mv in picking.move_ids_without_package:
                mv.write({"location_id": final_source.id})

            created_replenish = False
            # Si la source finale est une boutique ≠ CENTRAL → créer réassort pour le manquant
            if final_source and central and final_source.id != central.id:
                moves_data = []
                for pid, need in req.items():
                    prod = self.env["product.product"].browse(pid)
                    have = available_qty(prod, final_source)
                    missing = max(0.0, need - have)
                    if missing > 0:
                        moves_data.append((0, 0, {
                            "name": "%s → %s : %s" % (central.display_name, final_source.display_name, prod.display_name),
                            "product_id": prod.id,
                            "product_uom": prod.uom_id.id,
                            "product_uom_qty": missing,
                            "location_id": central.id,
                            "location_dest_id": final_source.id,
                        }))
                if moves_data:
                    # Chercher un type de picking interne du même entrepôt que la livraison si possible
                    picking_type_internal = self.env["stock.picking.type"].sudo().search([
                        ("code", "=", "internal"),
                        ("warehouse_id", "=", picking.picking_type_id.warehouse_id.id),
                    ], limit=1) or self.env["stock.picking.type"].sudo().search([("code", "=", "internal")], limit=1)

                    self.env["stock.picking"].sudo().create({
                        "picking_type_id": picking_type_internal.id if picking_type_internal else False,
                        "location_id": central.id,
                        "location_dest_id": final_source.id,
                        "origin": (picking.name or picking.origin or "") + " / Réassort auto",
                        "move_ids_without_package": moves_data,
                    })
                    created_replenish = True

            # Tenter une réservation immédiate (pour éviter “aucune quantité réservée”)
            try:
                picking.action_assign()
            except Exception as e:
                picking._quelyos_log_event("assign_error", {"exp": "Erreur à la réservation auto", "erreur": str(e)})

            # Log final
            picking._quelyos_log_event("auto_source", {
                "exp": "Sélection source automatique",
                "strategie": strategy,
                "basis": basis,
                "central": central and central.display_name or False,
                "choisie": final_source.display_name if final_source else False,
                "reassort_cree": created_replenish,
                "scores": coverage_score,
            })
            picking.message_post(body=_(
                "📦 Stratégie Qelyos : source '%(src)s' (règle : %(rule)s).%(reassort)s",
                src=final_source.display_name,
                rule=strategie_appliquee,
                reassort=" Réassort créé." if created_replenish else ""
            ))

    # -- Journal (dans champ + chatter)
    def _quelyos_log_event(self, event, extra=None):
        msg = "[QUELYOS][%s] %s" % (event.upper(), extra or {})
        for rec in self:
            rec.quelyos_log = (rec.quelyos_log or "") + (("\n" if rec.quelyos_log else "") + msg)
            rec.message_post(body=msg)

    # -- Contrôle “ordre strict” avant validation (option legacy strict_order)
    def _quelyos_check_strict_order_before_validate(self):
        self.ensure_one()
        if not self.group_id and not self.origin:
            return
        domain = [("id", "!=", self.id), ("state", "not in", ("done", "cancel"))]
        if self.group_id:
            domain += [("group_id", "=", self.group_id.id)]
        else:
            domain += [("origin", "=", self.origin)]
        if self.picking_type_id and self.picking_type_id.sequence:
            domain += [("picking_type_id.sequence", "<", self.picking_type_id.sequence)]
        blockers = self.search(domain, limit=1)
        if blockers:
            raise UserError(_("Ordre strict : vous devez d'abord terminer '%s' (type : %s).")
                            % (blockers.display_name, blockers.picking_type_id.display_name))


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # -- Après confirmation, appliquer/re-appliquer la stratégie sur les livraisons générées
    def _action_confirm(self):
        res = super()._action_confirm()
        pickings = self.mapped("picking_ids").filtered(lambda p: p.picking_type_id.code == "outgoing")
        for p in pickings:
            p._quelyos_apply_auto_source_strategy()
        return res
