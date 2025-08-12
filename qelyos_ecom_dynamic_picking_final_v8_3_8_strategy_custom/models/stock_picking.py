# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from collections import defaultdict

class StockPicking(models.Model):
    _inherit = "stock.picking"

    qelyos_dynamic_pick_mode = fields.Char(compute="_compute_qelyos_dynamic_pick_mode", string="Qelyos Mode")

    # --- Helpers ---
    def _is_website_origin(self):
        self.ensure_one()
        sale = self.sale_id
        return bool(getattr(sale, "website_id", False)) if sale else False

    def _qelyos_apply_scope(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        if not company.ecom_dynamic_enabled:
            return False
        if company.ecom_dynamic_only_website and not self._is_website_origin():
            return False
        return True

    def _compute_qelyos_dynamic_pick_mode(self):
        for picking in self:
            if not picking._qelyos_apply_scope():
                picking.qelyos_dynamic_pick_mode = ""
                continue
            company = picking.company_id or self.env.company
            if picking.picking_type_code == "outgoing":
                picking.qelyos_dynamic_pick_mode = dict(company._fields["ecom_dynamic_out_steps"].selection).get(company.ecom_dynamic_out_steps, "")
            elif picking.picking_type_code == "internal":
                picking.qelyos_dynamic_pick_mode = dict(company._fields["ecom_dynamic_pick_steps"].selection).get(company.ecom_dynamic_pick_steps, "")
            else:
                picking.qelyos_dynamic_pick_mode = ""

    # Availability per product at a location (including children)
    def _qelyos_available_by_product(self, location):
        Quant = self.env["stock.quant"]
        res = defaultdict(float)
        if not location:
            return res
        quants = Quant.search([
            ("location_id", "child_of", location.id),
            ("quantity", ">", 0),
        ])
        for q in quants:
            res[q.product_id.id] += max(q.quantity - q.reserved_quantity, 0.0)
        return res

    def _qelyos_required_by_product(self):
        req = defaultdict(float)
        for m in self.move_ids_without_package.filtered(lambda m: m.state not in ("done","cancel")):
            req[m.product_id.id] += m.product_uom_qty
        return req

    def _qelyos_locations_from_config(self):
        self.ensure_one()
        # Expect names like "CENT/Stock", "CENT/Stock/Boutique Gafsa", etc.
        names_priority = [
            "CENT/Stock",  # central
            "CENT/Stock/Boutique Gafsa",
            "CENT/Stock/Boutique Sousse",
            "CENT/Stock/Boutique Soukra",
        ]
        locs = {}
        for name in names_priority:
            locs[name] = self.env["stock.location"].search([("complete_name", "=", name)], limit=1)
        return locs

    def _qelyos_choose_source_location(self, req_by_prod):
        self.ensure_one()
        locs = self._qelyos_locations_from_config()
        central = locs.get("CENT/Stock")
        gafsa = locs.get("CENT/Stock/Boutique Gafsa")
        sousse = locs.get("CENT/Stock/Boutique Sousse")
        soukra = locs.get("CENT/Stock/Boutique Soukra")
        boutiques = [l for l in [gafsa, sousse, soukra] if l]

        # Critère 1: central can cover all lines
        if central:
            avail_c = self._qelyos_available_by_product(central)
            if all(avail_c.get(pid,0.0) >= qty for pid, qty in req_by_prod.items()):
                return ("central_full", central, None, None)

        # Critère 3 (ordre strict): try Gafsa -> Sousse -> Soukra for full coverage
        for loc in [gafsa, sousse, soukra]:
            if not loc:
                continue
            avail = self._qelyos_available_by_product(loc)
            if all(avail.get(pid,0.0) >= qty for pid, qty in req_by_prod.items()):
                return ("boutique_full", loc, None, None)

        # Critère 2: pick boutique with max available (partial), excluding central
        best_loc = None
        best_cover = -1.0
        for loc in boutiques:
            avail = self._qelyos_available_by_product(loc)
            cover = sum(min(avail.get(pid,0.0), qty) for pid, qty in req_by_prod.items())
            if cover > best_cover:
                best_cover = cover
                best_loc = loc

        # If none covers fully, create replenishment to Soukra for missing
        return ("partial_then_replenish", best_loc, soukra, central)

    def _qelyos_force_source_location(self, location):
        # Set the move source location to chosen location (overlay without touching routes)
        for m in self.move_ids_without_package.filtered(lambda m: m.state not in ("done","cancel")):
            if location:
                m.location_id = location.id

    def _qelyos_create_replenishment(self, dest_location, src_location, req_by_prod):
        if not (dest_location and src_location):
            return False
        # Compute missing at destination
        avail_dest = self._qelyos_available_by_product(dest_location)
        missing = {pid: max(qty - avail_dest.get(pid,0.0), 0.0) for pid, qty in req_by_prod.items()}
        missing = {pid: qty for pid, qty in missing.items() if qty > 0}
        if not missing:
            return False

        PickingType = self.env["stock.picking.type"]
        # generic internal picking type
        ptype = PickingType.search([("code", "=", "internal"), ("warehouse_id.company_id","=", self.company_id.id)], limit=1)
        if not ptype:
            ptype = PickingType.search([("code","=","internal")], limit=1)
        picking_vals = {
            "picking_type_id": ptype.id if ptype else False,
            "company_id": self.company_id.id,
            "location_id": src_location.id,
            "location_dest_id": dest_location.id,
            "origin": (self.origin or self.name) + " - Auto Replenishment to Soukra",
        }
        new_pick = self.env["stock.picking"].create(picking_vals)
        Move = self.env["stock.move"]
        for pid, qty in missing.items():
            Move.create({
                "name": "Replenish %s" % self.env["product.product"].browse(pid).display_name,
                "product_id": pid,
                "product_uom": self.env["product.product"].browse(pid).uom_id.id,
                "product_uom_qty": qty,
                "picking_id": new_pick.id,
                "location_id": src_location.id,
                "location_dest_id": dest_location.id,
                "company_id": self.company_id.id,
            })
        new_pick.action_confirm()
        if self.company_id.ecom_dynamic_dual_log:
            self.message_post(body=_("Qelyos: Created internal replenishment %s from %s to %s for missing qtys.") % (new_pick.name, src_location.display_name, dest_location.display_name))
        return new_pick

    def action_assign(self):
        res = super().action_assign()
        for picking in self:
            if not picking._qelyos_apply_scope() or picking.picking_type_code != "outgoing":
                continue
            req = picking._qelyos_required_by_product()
            mode, chosen, dest_soukra, src_central = picking._qelyos_choose_source_location(req)

            if mode in ("central_full", "boutique_full"):
                if chosen:
                    picking._qelyos_force_source_location(chosen)
                    res2 = super(StockPicking, picking).action_assign()
                    if picking.company_id.ecom_dynamic_dual_log:
                        picking.message_post(body=_("Qelyos: Reserved from %s (mode %s).") % (chosen.display_name, mode))
                    return res2

            elif mode == "partial_then_replenish":
                if chosen:
                    picking._qelyos_force_source_location(chosen)
                    super(StockPicking, picking).action_assign()
                    if picking.company_id.ecom_dynamic_dual_log:
                        picking.message_post(body=_("Qelyos: Partially reserved from %s; creating replenishment to Soukra.") % (chosen.display_name))
                # Always create replenishment to Soukra for missing
                picking._qelyos_create_replenishment(dest_soukra, src_central, req)
        return res
