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
        # Apply auto-source strategy for outgoing deliveries after creation (when moves exist)
        for rec in records.filtered(lambda r: r.picking_type_id and r.picking_type_id.code == "outgoing"):
            rec._quelyos_apply_auto_source_strategy()
        return records

    def action_assign(self):
        res = super().action_assign()
        for rec in self:
            rec._quelyos_log_event("assign", {"reserved": bool(rec.reserved_move_line_ids)})
        return res

    def button_validate(self):
        # Strict global order between pickings
        if self.env["ir.config_parameter"].sudo().get_param("quelyos_ecom_dynamic_picking.strict_order"):
            for picking in self:
                picking._quelyos_check_strict_order_before_validate()
        res = super().button_validate()
        for rec in self:
            rec._quelyos_log_event("validate", {"state": rec.state})
        return res

    # ----------------- Core logic -----------------
    def _quelyos_apply_auto_source_strategy(self):
        P = self.env["ir.config_parameter"].sudo()
        strategy = P.get_param("quelyos_ecom_dynamic_picking.strategy", "custom")
        only_web = P.get_param("quelyos_ecom_dynamic_picking.only_website")
        if strategy == "disabled":
            return

        # Optionally restrict to website orders only
        sale = self.sale_id if "sale_id" in self._fields else False
        if only_web and sale and not sale.website_id:
            return

        # Load configuration
        basis = P.get_param("quelyos_ecom_dynamic_picking.stock_basis", "free")
        central_id = int(P.get_param("quelyos_ecom_dynamic_picking.central_location_id") or 0)
        shop_ids = [int(x) for x in (P.get_param("quelyos_ecom_dynamic_picking.shop_ids") or "").split(",") if x]
        strict_names_enabled = P.get_param("quelyos_ecom_dynamic_picking.strict_shop_order_enabled") == "1"
        order_names = (P.get_param("quelyos_ecom_dynamic_picking.shop_order_names") or "").replace(">", ",")
        priority_names = [n.strip() for n in order_names.split(",") if n.strip()] if order_names else []

        Loc = self.env["stock.location"].sudo()
        central = Loc.browse(central_id) if central_id else Loc.browse(False)
        shops = Loc.browse(shop_ids)

        if not (central or shops):
            return  # nothing configured

        # Aggregate required quantities per product
        req = {}
        for move in self.move_ids_without_package:
            product = move.product_id
            qty = move.product_uom._compute_quantity(move.product_uom_qty, product.uom_id)
            req[product.id] = req.get(product.id, 0.0) + qty

        # Helper to get availability at a location
        def available_qty(product, location):
            if not location:
                return 0.0
            if basis == "onhand":
                quants = self.env["stock.quant"].sudo().read_group(
                    [("product_id", "=", product.id), ("location_id", "child_of", location.id)],
                    ["quantity:sum"], ["location_id"]
                )
                return (quants and quants[0].get("quantity", 0.0)) or 0.0
            elif basis == "free":
                quants = self.env["stock.quant"].sudo().read_group(
                    [("product_id", "=", product.id), ("location_id", "child_of", location.id)],
                    ["quantity:sum", "reserved_quantity:sum"], ["location_id"]
                )
                if not quants:
                    return 0.0
                return (quants[0].get("quantity", 0.0) or 0.0) - (quants[0].get("reserved_quantity", 0.0) or 0.0)
            else:  # forecast
                prod = product.with_context(location=location.id)
                return prod.virtual_available

        # Check central full coverage
        central_ok = False
        if central:
            central_ok = all(available_qty(self.env["product.product"].browse(pid), central) >= need for pid, need in req.items())

        # Choose shop
        chosen_shop = False
        coverage_score = {}
        if not central_ok and shops:
            # Strict name order first (find first that covers all)
            if strict_names_enabled and priority_names:
                for name in priority_names:
                    shop = shops.filtered(lambda l: l.complete_name.endswith(name) or l.name == name)[:1]
                    if shop:
                        ok = all(available_qty(self.env["product.product"].browse(pid), shop) >= need for pid, need in req.items())
                        if ok:
                            chosen_shop = shop
                            break
            # Else or fallback: choose max coverage
            if not chosen_shop:
                best_shop = False
                best_score = -1.0
                for shop in shops:
                    score = 0.0
                    for pid, need in req.items():
                        have = available_qty(self.env["product.product"].browse(pid), shop)
                        score += min(have, need)
                    coverage_score[shop.id] = score
                    if score > best_score:
                        best_score = score
                        best_shop = shop
                chosen_shop = best_shop

        # Decide final source location
        final_source = False
        strategy_applied = ""
        if central_ok:
            final_source = central
            strategy_applied = "central_full"
        elif chosen_shop:
            final_source = chosen_shop
            strategy_applied = "best_shop_or_strict"
        elif central:
            final_source = central
            strategy_applied = "central_fallback"
        else:
            final_source = shops[:1] if shops else False
            strategy_applied = "first_available"

        if not final_source:
            return

        # Repoint picking + moves to final_source
        self.write({"location_id": final_source.id})
        for mv in self.move_ids_without_package:
            mv.write({"location_id": final_source.id})

        # Create internal replenishment from central to shop if chosen shop is not central and shortages exist
        created_replenish = False
        if final_source and central and final_source.id != central.id:
            moves_data = []
            for pid, need in req.items():
                prod = self.env["product.product"].browse(pid)
                have = available_qty(prod, final_source)
                missing = max(0.0, need - have)
                if missing > 0:
                    qty = missing
                    moves_data.append((0, 0, {
                        "name": "%s → %s : %s" % (central.display_name, final_source.display_name, prod.display_name),
                        "product_id": prod.id,
                        "product_uom": prod.uom_id.id,
                        "product_uom_qty": qty,
                        "location_id": central.id,
                        "location_dest_id": final_source.id,
                    }))
            if moves_data:
                picking_type = self.env["stock.picking.type"].sudo().search([
                    ("code", "=", "internal"),
                    ("warehouse_id", "=", self.picking_type_id.warehouse_id.id),
                ], limit=1) or self.env["stock.picking.type"].sudo().search([("code", "=", "internal")], limit=1)
                self.env["stock.picking"].sudo().create({
                    "picking_type_id": picking_type.id if picking_type else False,
                    "location_id": central.id,
                    "location_dest_id": final_source.id,
                    "origin": (self.name or self.origin or "") + " / Replenish",
                    "move_ids_without_package": moves_data,
                })
                created_replenish = True

        # Log
        self._quelyos_log_event("auto_source", {
            "strategy": strategy,
            "basis": basis,
            "central": central and central.display_name,
            "chosen": final_source.display_name if final_source else False,
            "replenishment_created": created_replenish,
            "coverage": coverage_score
        })

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
        # After pickings are generated, apply auto source strategy if enabled
        pickings = self.mapped("picking_ids").filtered(lambda p: p.picking_type_id.code == "outgoing")
        for p in pickings:
            p._quelyos_apply_auto_source_strategy()
        return res
