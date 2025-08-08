# qelyos_ecom_dynamic_picking/models/sale_order.py
from odoo import api, fields, models, _

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ecom_dynamic_source_location_ids = fields.Many2many(
        "stock.location",
        string="Emplacements sources (magasins) pour le web",
        domain=[("usage", "=", "internal")],
        help="Liste ordonnée des magasins candidats (Soukra/Sousse/Gafsa...)."
    )
    ecom_dynamic_strategy = fields.Selection(
        [
            ("full_first", "Magasin pouvant tout couvrir (sinon meilleur taux de couverture)"),
            ("max_cover", "Toujours le meilleur taux de couverture"),
        ],
        default="full_first",
        string="Stratégie de sélection"
    )
    ecom_dynamic_only_website = fields.Boolean(
        string="Appliquer uniquement aux commandes web",
        default=True,
        help="Si coché, n'applique la logique que pour les commandes créées via website_sale."
    )
    ecom_dynamic_switch_picking_type = fields.Boolean(
        string="Basculer le type d'opération selon le magasin",
        default=True,
        help="Si vous avez des picking types 'Expédition Web – Soukra/Sousse/Gafsa', on bascule automatiquement."
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        ICP = self.env["ir.config_parameter"].sudo()
        loc_ids_str = ICP.get_param("qelyos_ecom_dynamic_picking.source_location_ids", default="")
        strategy = ICP.get_param("qelyos_ecom_dynamic_picking.strategy", default="full_first")
        only_web = ICP.get_param("qelyos_ecom_dynamic_picking.only_website", default="True")
        switch_pt = ICP.get_param("qelyos_ecom_dynamic_picking.switch_picking_type", default="True")
        loc_ids = [int(x) for x in loc_ids_str.split(",") if x.strip().isdigit()]
        res.update({
            "ecom_dynamic_source_location_ids": [(6, 0, loc_ids)],
            "ecom_dynamic_strategy": strategy or "full_first",
            "ecom_dynamic_only_website": True if str(only_web) in ("True","1","true") else False,
            "ecom_dynamic_switch_picking_type": True if str(switch_pt) in ("True","1","true") else False,
        })
        return res

    def set_values(self):
        super().set_values()
        ICP = self.env["ir.config_parameter"].sudo()
        loc_ids = ",".join(str(x) for x in self.ecom_dynamic_source_location_ids.ids)
        ICP.set_param("qelyos_ecom_dynamic_picking.source_location_ids", loc_ids)
        ICP.set_param("qelyos_ecom_dynamic_picking.strategy", self.ecom_dynamic_strategy or "full_first")
        ICP.set_param("qelyos_ecom_dynamic_picking.only_website", "True" if self.ecom_dynamic_only_website else "False")
        ICP.set_param("qelyos_ecom_dynamic_picking.switch_picking_type", "True" if self.ecom_dynamic_switch_picking_type else "False")


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _is_website_order(self):
        self.ensure_one()
        return bool(self.website_id)

    def _get_dynamic_source_locations(self):
        ICP = self.env["ir.config_parameter"].sudo()
        loc_ids_str = ICP.get_param("qelyos_ecom_dynamic_picking.source_location_ids", default="")
        ids = [int(x) for x in loc_ids_str.split(",") if x.strip().isdigit()]
        return self.env["stock.location"].browse(ids)

    def _get_dynamic_strategy(self):
        ICP = self.env["ir.config_parameter"].sudo()
        return ICP.get_param("qelyos_ecom_dynamic_picking.strategy", default="full_first")

    def _should_only_website(self):
        ICP = self.env["ir.config_parameter"].sudo()
        return ICP.get_param("qelyos_ecom_dynamic_picking.only_website", default="True") in ("True", "1", True)

    def _switch_picking_type(self):
        ICP = self.env["ir.config_parameter"].sudo()
        return ICP.get_param("qelyos_ecom_dynamic_picking.switch_picking_type", default="True") in ("True", "1", True)

    def _compute_free_qty_at_location(self, product, location):
        # Quantité libre (non réservée) à un emplacement (avec enfants)
        product_ctx = product.with_context(location=location.id, compute_child=True)
        # free_qty est disponible sur v18; fallback qty_available si besoin
        free = getattr(product_ctx, "free_qty", None)
        if free is None:
            free = product_ctx.qty_available
        return free

    def _best_location_for_order(self, locations, strategy=None):
        self.ensure_one()
        lines = self.order_line.filtered(lambda l: l.product_id.type == "product" and l.product_uom_qty > 0)
        if not lines:
            return False

        if not strategy:
            strategy = self._get_dynamic_strategy() or "full_first"

        # 1) Chercher un emplacement qui couvre 100%
        candidates_full = []
        for loc in locations:
            ok_all = True
            for l in lines:
                need = l.product_uom_qty
                have = self._compute_free_qty_at_location(l.product_id, loc)
                if have < need:
                    ok_all = False
                    break
            if ok_all:
                candidates_full.append(loc)

        if strategy == "full_first" and candidates_full:
            return candidates_full[0]

        # 2) Meilleur taux de couverture
        best_loc, best_score = False, -1.0
        for loc in locations:
            covered = 0.0
            total = 0.0
            for l in lines:
                need = l.product_uom_qty
                have = self._compute_free_qty_at_location(l.product_id, loc)
                covered += min(have, need)
                total += need
            score = (covered / total) if total else 0.0
            if score > best_score:
                best_score = score
                best_loc = loc
        return best_loc

    def _find_picking_type_for_location(self, location):
        PickingType = self.env["stock.picking.type"]
        ptype = PickingType.search([
            ("code", "=", "outgoing"),
            ("default_location_src_id", "=", location.id),
        ], limit=1)
        return ptype or False

    def action_confirm(self):
        res = super().action_confirm()

        for order in self:
            if order._should_only_website() and not order._is_website_order():
                continue

            locations = order._get_dynamic_source_locations()
            if not locations:
                continue

            best_loc = order._best_location_for_order(locations)
            if not best_loc:
                continue

            pickings = order.picking_ids.filtered(lambda p: p.picking_type_code == "outgoing" and p.state in ("confirmed", "waiting", "assigned"))
            if not pickings:
                continue

            for picking in pickings:
                # Unreserve before changing locations
                if hasattr(picking, "action_unreserve"):
                    picking.action_unreserve()
                elif hasattr(picking, "_action_cancel_reservation"):
                    picking._action_cancel_reservation()

                if self._switch_picking_type():
                    ptype = order._find_picking_type_for_location(best_loc)
                    if ptype:
                        picking.picking_type_id = ptype.id
                        # also ensure locations align with picking type defaults if needed

                # Force each move source location
                for move in picking.move_ids_without_package:
                    move.location_id = best_loc.id

                # Re-assign
                picking.action_assign()

        return res