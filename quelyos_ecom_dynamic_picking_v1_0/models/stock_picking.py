# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = "stock.picking"

    quelyos_log = fields.Text(string="Quelyos Dual Log (local)")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._quelyos_log_event("create", {"origin": rec.origin, "type": rec.picking_type_id and rec.picking_type_id.display_name})
        for rec in records.filtered(lambda r: r.picking_type_id and r.picking_type_id.code == "outgoing"):
            rec._quelyos_apply_auto_source_strategy()
        return records

    def action_assign(self):
        res = super().action_assign()
        for rec in self:
            # Réservé si au moins un move est 'assigned' ou 'partially_available'
            reserved = any(m.state in ('assigned', 'partially_available') for m in rec.move_ids_without_package)
            # Somme des quantités effectivement réservées sur les move lines (Odoo 18)
            reserved_qty = sum(rec.move_line_ids.mapped('reserved_qty') or [0.0])
            rec._quelyos_log_event("assign", {
                "reserved": reserved,
                "reserved_qty": reserved_qty
            })
        return res

    def button_validate(self):
        if self.env["ir.config_parameter"].sudo().get_param("quelyos_ecom_dynamic_picking.strict_order"):
            for picking in self:
                picking._quelyos_check_strict_order_before_validate()
        res = super().button_validate()
        for rec in self:
            rec._quelyos_log_event("validate", {"state": rec.state})
        return res

    # Core: auto source selection + internal replenishment
    def _quelyos_apply_auto_source_strategy(self):
    """
    Applique la stratégie de sélection automatique de l’emplacement source
    pour les livraisons sortantes (pickings) selon la configuration Qelyos.
    
    Exp :
    - Si CENT/Stock couvre toute la commande → on prend CENT comme source.
    - Sinon, on choisit la boutique avec le maximum de stock libre (ou l'ordre strict si activé).
    - Si la boutique ne couvre pas tout → déclenchement d’un réassort interne.
    """

    P = self.env["ir.config_parameter"].sudo()

    def _qget(key, default=None):
        """
        Helper pour récupérer une clé de config, compatible avec :
        - Ancienne notation : quelyos_ecom_dynamic_picking.<clé>
        - Nouvelle notation : quelyos_dynamic_<clé>
        
        Exp :
        _qget("strategy", "custom") → lit d'abord "quelyos_dynamic_strategy",
        sinon "quelyos_ecom_dynamic_picking.strategy", sinon renvoie "custom".
        """
        v = P.get_param(f"quelyos_dynamic_{key}")
        if v in (None, "", False):
            v = P.get_param(f"quelyos_ecom_dynamic_picking.{key}")
        return v if v not in (None, "") else default

    # Lecture des paramètres
    strategy   = _qget("strategy", "custom")
    only_web   = _qget("only_website", "False") in ("1", "True", "true")
    basis      = _qget("stock_basis", "free")

    central_id = int(_qget("central_location_id", 0) or 0)

    shop_ids_csv = _qget("shop_ids", "")
    shop_ids = [int(x) for x in shop_ids_csv.split(",") if x]

    strict_names_enabled = _qget("strict_shop_order_enabled", "False") in ("1", "True", "true")
    order_names = (_qget("shop_order_names", "") or "").replace(">", ",")
    priority_names = [n.strip() for n in order_names.split(",") if n.strip()]

    def available_qty(product, location):
        """
        Retourne la quantité dispo selon la base de calcul configurée :
        - free     → quantité libre (qty dispo - réservée)
        - onhand   → quantité physique réelle
        - forecast → stock prévisionnel (virtual_available)
        """
        if basis == "free":
            return product.with_context(location=location.id, compute_child=True).free_qty
        elif basis == "onhand":
            return product.with_context(location=location.id, compute_child=True).qty_available
        elif basis == "forecast":
            return product.with_context(location=location.id, compute_child=True).virtual_available
        return 0.0

    for picking in self:
        if picking.picking_type_code != "outgoing":
            continue
        if strategy != "custom":
            continue
        if only_web and not getattr(picking.sale_id, "website_id", False):
            continue

        central_loc = self.env["stock.location"].browse(central_id) if central_id else None
        shop_locs = self.env["stock.location"].browse(shop_ids)

        # --- Critère 1 : tester CENT/Stock ---
        central_ok = central_loc and all(
            available_qty(move.product_id, central_loc) >= move.product_uom_qty
            for move in picking.move_ids_without_package
        )

        if central_ok:
            picking.location_id = central_loc
            picking.message_post(
                body=f"📦 Stratégie Qelyos : CENT/Stock sélectionné (stock suffisant)."
            )
            continue

        # --- Critère 2 : boutiques ---
        best_shop = None
        best_score = -1

        if strict_names_enabled and priority_names:
            # --- Mode ordre strict ---
            for name in priority_names:
                shop = shop_locs.filtered(lambda l: l.name.strip().lower() == name.lower())
                if not shop:
                    continue
                if all(
                    available_qty(move.product_id, shop) >= move.product_uom_qty
                    for move in picking.move_ids_without_package
                ):
                    best_shop = shop[0]
                    break
        else:
            # --- Mode meilleur score ---
            for shop in shop_locs:
                total_qty = sum(
                    max(0, available_qty(move.product_id, shop))
                    for move in picking.move_ids_without_package
                )
                if total_qty > best_score:
                    best_score = total_qty
                    best_shop = shop

        if best_shop:
            picking.location_id = best_shop
            picking.message_post(
                body=f"📦 Stratégie Qelyos : Boutique '{best_shop.name}' sélectionnée."
            )

            # Vérif si réassort nécessaire
            for move in picking.move_ids_without_package:
                dispo = available_qty(move.product_id, best_shop)
                if dispo < move.product_uom_qty and central_loc:
                    missing = move.product_uom_qty - dispo
                    internal_type = self.env["stock.picking.type"].search(
                        [
                            ("code", "=", "internal"),
                            ("warehouse_id", "=", best_shop.get_warehouse().id)
                        ], limit=1
                    )
                    if internal_type:
                        self.env["stock.picking"].create({
                            "picking_type_id": internal_type.id,
                            "location_id": central_loc.id,
                            "location_dest_id": best_shop.id,
                            "origin": f"Réassort auto pour {picking.name}",
                            "move_ids_without_package": [(0, 0, {
                                "product_id": move.product_id.id,
                                "name": move.product_id.display_name,
                                "product_uom": move.product_uom.id,
                                "product_uom_qty": missing,
                            })]
                        })
                        picking.message_post(
                            body=f"♻️ Réassort interne créé depuis CENT vers {best_shop.name} "
                                 f"({missing} x {move.product_id.display_name})"
                        )


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
            raise UserError(_("Ordre strict: vous devez d'abord terminer '%s' (type: %s).")
                            % (blockers.display_name, blockers.picking_type_id.display_name))


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_confirm(self):
        res = super()._action_confirm()
        pickings = self.mapped("picking_ids").filtered(lambda p: p.picking_type_id.code == "outgoing")
        for p in pickings:
            p._quelyos_apply_auto_source_strategy()
        return res
