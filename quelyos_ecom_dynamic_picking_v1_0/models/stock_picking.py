# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.exceptions import UserError, ValidationError

class StockPicking(models.Model):
    _inherit = "stock.picking"

    quelyos_log = fields.Text(string=_("Quelyos Dual Log (local)"))
    quelyos_reassort_picking_id = fields.Many2one("stock.picking", string=_("Picking de réassort"), copy=False)
    
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        
        params = self.env["ir.config_parameter"].sudo()
        only_web = params.get_param("quelyos_ecom_dynamic_picking.only_website")
        strategy = params.get_param("quelyos_ecom_dynamic_picking.strategy", "disabled")
        
        for rec in records:
            is_website_order = rec.sale_id and rec.sale_id.website_id
            if strategy == "custom_criteria" and (not only_web or is_website_order):
                rec._quelyos_select_source_location()
                
            if params.get_param("quelyos_ecom_dynamic_picking.dual_log"):
                rec._quelyos_dual_log("create", extra={
                    "origin": rec.origin, "picking_type": rec.picking_type_id.display_name,
                    "source_location": rec.location_id.name,
                })
        return records

    def write(self, vals):
        res = super(StockPicking, self).write(vals)
        if 'location_id' in vals:
            allowed_ids_str = self.env["ir.config_parameter"].sudo().get_param("quelyos_ecom_dynamic_picking.allowed_src_ids") or ""
            allowed_ids = [int(x) for x in allowed_ids_str.split(",") if x]
            if allowed_ids and vals.get('location_id') and vals['location_id'] not in allowed_ids:
                raise ValidationError(_("L'emplacement source sélectionné n'est pas autorisé."))
        return res

    def action_assign(self):
        res = super().action_assign()
        if self.env["ir.config_parameter"].sudo().get_param("quelyos_ecom_dynamic_picking.dual_log"):
            for rec in self:
                rec._quelyos_dual_log("assign", extra={"reserved": bool(rec.reserved_move_line_ids)})
        return res

    def button_validate(self):
        if self.env["ir.config_parameter"].sudo().get_param("quelyos_ecom_dynamic_picking.strict_order"):
            for picking in self:
                picking._quelyos_check_strict_order_before_validate()
        res = super().button_validate()
        if self.env["ir.config_parameter"].sudo().get_param("quelyos_ecom_dynamic_picking.dual_log"):
            for rec in self:
                rec._quelyos_dual_log("validate", extra={"state": rec.state})
        return res

    def _quelyos_dual_log(self, event, extra=None):
        """ Log an event and post a message on the picking. """
        msg = "[QUELYOS][%s] %s" % (event.upper(), extra or {})
        for rec in self:
            rec.quelyos_log = (rec.quelyos_log or "") + (("\n" if rec.quelyos_log else "") + msg)
            rec.message_post(body=msg)

    def _quelyos_check_strict_order_before_validate(self):
        """
        Checks if other related pickings in the same group or with the same origin
        need to be validated first, based on picking type sequence.
        """
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

    def _quelyos_select_source_location(self):
        self.ensure_one()
        # Ne s'applique qu'aux pickings OUT (livraisons)
        if self.picking_type_id.code != "outgoing":
            return
        
        params = self.env["ir.config_parameter"].sudo()
        stock_basis = params.get_param("quelyos_ecom_dynamic_picking.stock_basis", "free_quantity")
        shop_ids = [int(x) for x in params.get_param("quelyos_ecom_dynamic_picking.shop_locations").split(",") if x]
        shops = self.env["stock.location"].browse(shop_ids)
        cent_location = self.env.ref("stock.stock_location_stock") # Assumons que CENT est l'emplacement par défaut

        # Calculer les quantités demandées
        demand_qties = {line.product_id.id: line.product_qty for line in self.move_lines}
        
        def get_stock_qty(location, product_id):
            product = self.env["product.product"].browse(product_id)
            if stock_basis == "free_quantity":
                return product.with_context(location=location.id).free_qty
            elif stock_basis == "on_hand":
                return product.with_context(location=location.id).qty_available
            elif stock_basis == "forecast":
                return product.with_context(location=location.id).virtual_available
            return 0

        # Critère 1 : CENT a assez de stock ?
        cent_is_sufficient = True
        for product_id, qty in demand_qties.items():
            if get_stock_qty(cent_location, product_id) < qty:
                cent_is_sufficient = False
                break
        
        if cent_is_sufficient:
            self.location_id = cent_location
            self._quelyos_dual_log("strategy_applied", extra={"strategy": "CENT", "location": cent_location.name})
            return

        # Critère 2 & 3 : Chercher la meilleure boutique
        best_shop = False
        max_stock_cumulated = -1
        
        shops_to_check = shops
        # Si Ordre strict est activé, l'ordre est défini par les IDs dans la liste
        # Le champ Many2many stocke les IDs dans l'ordre d'ajout
        
        for shop in shops_to_check:
            is_sufficient = True
            current_cumulated_stock = 0
            for product_id, qty in demand_qties.items():
                stock_available = get_stock_qty(shop, product_id)
                current_cumulated_stock += min(stock_available, qty)
                if stock_available < qty:
                    is_sufficient = False
            
            if is_sufficient:
                self.location_id = shop
                self._quelyos_dual_log("strategy_applied", extra={"strategy": "Shop", "location": shop.name})
                return

            if current_cumulated_stock > max_stock_cumulated:
                max_stock_cumulated = current_cumulated_stock
                best_shop = shop

        # Si aucune boutique ne couvre tout, on choisit la meilleure
        if best_shop:
            self.location_id = best_shop
            self._quelyos_dual_log("strategy_applied", extra={"strategy": "Best Shop", "location": best_shop.name})
            self._quelyos_create_reassort_picking(best_shop, demand_qties, stock_basis, cent_location)
        else:
            self.location_id = cent_location
            self._quelyos_dual_log("strategy_applied", extra={"strategy": "Fallback to CENT", "location": cent_location.name})

    def _quelyos_create_reassort_picking(self, shop_location, demand_qties, stock_basis, cent_location):
        """ Crée un picking de réassort si le stock de la boutique est insuffisant. """
        moves = []
        for product_id, qty in demand_qties.items():
            product = self.env["product.product"].browse(product_id)
            stock_available = self.env["product.product"].browse(product_id).with_context(location=shop_location.id).qty_available
            if qty > stock_available:
                missing_qty = qty - stock_available
                moves.append((0, 0, {
                    'product_id': product_id,
                    'product_uom_qty': missing_qty,
                    'name': product.name,
                    'location_id': cent_location.id,
                    'location_dest_id': shop_location.id,
                }))
        
        if moves:
            internal_picking_type = self.env["stock.picking.type"].search([
                ('warehouse_id', '=', self.picking_type_id.warehouse_id.id),
                ('code', '=', 'internal')
            ], limit=1)

            if internal_picking_type:
                reassort_picking = self.env["stock.picking"].create({
                    'location_id': cent_location.id,
                    'location_dest_id': shop_location.id,
                    'picking_type_id': internal_picking_type.id,
                    'origin': self.name,
                    'move_ids_without_package': moves,
                })
                self.quelyos_reassort_picking_id = reassort_picking
                self._quelyos_dual_log("reassort_created", extra={"reassort_picking": reassort_picking.name})
            else:
                self._quelyos_dual_log("error", extra={"message": "Impossible de trouver le type de picking interne."})


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_confirm(self):
        only_web = self.env["ir.config_parameter"].sudo().get_param("quelyos_ecom_dynamic_picking.only_website")
        res = super()._action_confirm()
        if only_web and not any(self.mapped("website_id")):
            return res
        return res
