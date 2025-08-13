# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = "stock.picking"

    quelyos_log = fields.Text(string="Quelyos – Journal (local)")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._quelyos_log_event("create", {
                "exp": "Création picking",
                "origine": rec.origin,
                "type": rec.picking_type_id and rec.picking_type_id.display_name
            })
        for rec in records.filtered(lambda r: r.picking_type_id and r.picking_type_id.code == "outgoing"):
            rec._quelyos_apply_auto_source_strategy()
        return records

    def action_assign(self):
        res = super().action_assign()
        for rec in self:
            reserved_flag = any(m.state in ('assigned', 'partially_available') for m in rec.move_ids_without_package)
            reserved_qty = sum(rec.move_line_ids.mapped('reserved_qty') or [0.0])
            rec._quelyos_log_event("assign", {
                "exp": "Vérifier la disponibilité",
                "reserved": reserved_flag,
                "reserved_qty": reserved_qty
            })
        return res

    def button_validate(self):
        if self.env["ir.config_parameter"].sudo().get_param("quelyos_ecom_dynamic_picking.strict_order"):
            for picking in self:
                picking._quelyos_check_strict_order_before_validate()
        res = super().button_validate()
        for rec in self:
            rec._quelyos_log_event("validate", {"exp": "Validation picking", "etat": rec.state})
        return res

    def _quelyos_apply_auto_source_strategy(self):
        """
        exp :
        - Si CENT/Stock couvre tout → source = CENT
        - Sinon → meilleure boutique (ou ordre strict si activé)
        - Si la boutique ne couvre pas tout → créer un réassort interne CENT → Boutique (manquant)
        """
        P = self.env["ir.config_parameter"].sudo()

        def _qget(key, default=None):
            v = P.get_param(f"quelyos_dynamic_{key}")
            if v in (None, "", False):
                v = P.get_param(f"quelyos_ecom_dynamic_picking.{key}")
            return v if v not in (None, "") else default

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
            elif basis == "forecast":
                return prod_ctx.virtual_available
            return 0.0

        for picking in self:
            if not picking.picking_type_id or picking.picking_type_id.code != "outgoing":
                continue
            if strategy != "custom":
                continue
            if only_web and not getattr(picking, "sale_id", False):
                continue
            if only_web and picking.sale_id and not getattr(picking.sale_id, "website_id", False):
                continue

            Loc = self.env["stock.location"].sudo()
            central = Loc.browse(central_id) if central_id else Loc.browse(False)
            shops = Loc.browse(shop_ids)

            if not (central or shops):
                self._quelyos_log_event("auto_source_skip", {
                    "exp": "Aucun emplacement central ni boutique configuré"
                })
                continue

            # Besoins par produit
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
                # Critère 3 : ordre strict
                if strict_names_enabled and priority_names:
                    for name in priority_names:
                        shop = shops.filtered(lambda l: l.name.strip().lower() == name.lower())[:1]
                        if shop:
                            ok = all(
                                available_qty(self.env["product.product"].browse(pid), shop) >= need
                                for pid, need in req.items()
                            )
                            if ok:
                                chosen_shop = shop
                                break

                # Meilleure boutique par score (somme des libres), avec tie-break couverture
                if not chosen_shop:
                    best_shop = False
                    best_score = -1.0
                    best_tiebreak_cover = -1.0
                    for shop in shops:
                        free_sum = 0.0
                        cover_sum = 0.0
                        for pid, need in req.items():
                            prod = self.env["product.product"].browse(pid)
                            have = available_qty(prod, shop)
                            free_sum += have
                            cover_sum += max(0.0, min(have, need))
                        coverage_score[shop.id] = {"free_sum": free_sum, "cover_sum": cover_sum}
                        if (free_sum > best_score) or (free_sum == best_score and cover_sum > best_tiebreak_cover):
                            best_score = free_sum
                            best_tiebreak_cover = cover_sum
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

            # Appliquer la source
            picking.write({"location_id": final_source.id})
            for mv in picking.move_ids_without_package:
                mv.write({"location_id": final_source.id})

            # Réassort si source != central
            created_replenish = False
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

            # Réserver tout de suite
            try:
                picking.action_assign()
            except Exception as e:
                picking._quelyos_log_event("assign_error", {"exp": "Erreur à la réservation auto", "erreur": str(e)})

            # Logs
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

    def _quelyos_log_event(self, event, extra=None):
        msg = "[QUELYOS][%s] %s" % (event.upper(), extra or {})
        for rec in self:
            rec.quelyos_log = (rec.quelyos_log or "") + (("\n" if rec.quelyos_log else "") + msg)
            rec.message_post(body=msg)

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

    def _action_confirm(self):
        res = super()._action_confirm()
        pickings = self.mapped("picking_ids").filtered(lambda p: p.picking_type_id.code == "outgoing")
        for p in pickings:
            p._quelyos_apply_auto_source_strategy()
        return res
