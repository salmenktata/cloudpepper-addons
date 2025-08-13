# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    quelyos_log = fields.Text(string="Log Qelyos", readonly=True)

    # ==============================
    # Auto-apply picking source strategy
    # ==============================
    @api.model
    def _get_param(self, key, default=None):
        """Helper to get system parameter safely"""
        return self.env['ir.config_parameter'].sudo().get_param(key, default)

    def _location_covers_all(self, location, required_products, basis):
        """Check if location can fulfill all products quantities based on stock basis"""
        Quant = self.env['stock.quant']
        for product, qty in required_products.items():
            domain = [
                ('product_id', '=', product.id),
                ('location_id', 'child_of', location.id)
            ]
            qty_available = 0.0
            if basis == 'free':
                domain += [('quantity', '>', 0)]
                qty_available = sum(Quant.search(domain).mapped('quantity')) - sum(
                    Quant.search(domain).mapped('reserved_quantity')
                )
            else:  # forecast
                qty_available = product.with_context(location=location.id).virtual_available
            if qty_available < qty:
                return False
        return True

    def _get_all_location_quantities(self, product):
        """Return quantities by location for a given product"""
        Quant = self.env['stock.quant']
        quants = Quant.search([
            ('product_id', '=', product.id),
            ('quantity', '>', 0),
            ('location_id.usage', '=', 'internal'),
        ])
        result = {}
        for q in quants:
            free_qty = q.quantity - q.reserved_quantity
            if q.location_id in result:
                result[q.location_id] += free_qty
            else:
                result[q.location_id] = free_qty
        return result

    def _quelyos_apply_auto_source_strategy(self):
        """Main entry for Qelyos picking auto source selection"""
        for picking in self:
            if picking.picking_type_code != 'outgoing':
                continue

            Param = self.env['ir.config_parameter'].sudo()

            # Config
            central_loc_id = int(Param.get_param('quelyos_dynamic_picking.central_location_id', '0'))
            basis = Param.get_param('quelyos_dynamic_picking.stock_basis', 'free')
            only_website = Param.get_param('quelyos_dynamic_picking.only_website', 'False') == 'True'

            # Shops from config (ordered)
            shop_ids_str = Param.get_param('quelyos_dynamic_picking.shop_ids', '[]')
            try:
                shop_ids = [int(x) for x in shop_ids_str.strip('[]').split(',') if x.strip()]
            except Exception:
                shop_ids = []
            shops = self.env['stock.location'].browse(shop_ids)

            # Only website condition
            if only_website and picking.sale_id and not picking.sale_id.website_id:
                continue

            # Prepare product requirements
            products_required = {}
            for ml in picking.move_ids_without_package:
                products_required[ml.product_id] = products_required.get(ml.product_id, 0.0) + ml.product_uom_qty

            candidate = None
            chosen_strategy = None

            # -------- Critère 1 : Central
            if central_loc_id:
                central_loc = self.env['stock.location'].browse(central_loc_id)
                if self._location_covers_all(central_loc, products_required, basis):
                    candidate = central_loc
                    chosen_strategy = "crit1_central"

            # -------- Critère 2 : Best shop by stock
            if not candidate:
                best_loc = None
                best_qty = -1
                for shop in shops:
                    total_qty = 0.0
                    ok = True
                    for product, qty in products_required.items():
                        loc_qty = self._get_all_location_quantities(product).get(shop, 0.0)
                        if loc_qty < qty:
                            ok = False
                            break
                        total_qty += loc_qty
                    if ok and total_qty > best_qty:
                        best_loc = shop
                        best_qty = total_qty
                if best_loc:
                    candidate = best_loc
                    chosen_strategy = "crit2_best_stock"

            # -------- Critère 3 : Order from config
            if not candidate and shops:
                for loc in shops:
                    if self._location_covers_all(loc, products_required, basis):
                        candidate = loc
                        chosen_strategy = "crit3_config_order"
                        break

            # -------- Critère 4 : Reassort (fallback)
            if not candidate and shops:
                # Take first shop and trigger internal transfer
                reassort_target = shops[0]
                self._quelyos_trigger_internal_reassort(central_loc_id, reassort_target, products_required)
                chosen_strategy = "crit4_reassort"

            # Apply candidate
            if candidate:
                picking.move_ids_without_package.write({'location_id': candidate.id})
                picking.quelyos_log = _("Source set to %s via %s") % (candidate.display_name, chosen_strategy)

    def _quelyos_trigger_internal_reassort(self, source_loc_id, target_loc, products_required):
        """Create an internal transfer from source to target for missing products"""
        if not source_loc_id:
            return
        source_loc = self.env['stock.location'].browse(source_loc_id)
        if not source_loc.exists():
            return

        PickingType = self.env['stock.picking.type']
        internal_type = PickingType.search([('code', '=', 'internal')], limit=1)
        if not internal_type:
            raise UserError(_("No internal transfer type found."))

        moves = []
        for product, qty in products_required.items():
            moves.append((0, 0, {
                'name': product.display_name,
                'product_id': product.id,
                'product_uom_qty': qty,
                'product_uom': product.uom_id.id,
                'location_id': source_loc.id,
                'location_dest_id': target_loc.id,
            }))

        picking_vals = {
            'picking_type_id': internal_type.id,
            'location_id': source_loc.id,
            'location_dest_id': target_loc.id,
            'move_ids_without_package': moves
        }
        self.env['stock.picking'].create(picking_vals)


# ==============================
# Config settings extension
# ==============================
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    quelyos_dynamic_central_location_id = fields.Many2one(
        'stock.location',
        string="Emplacement central (CENT/Stock)",
        domain="[('usage', '=', 'internal')]",
        config_parameter='quelyos_dynamic_picking.central_location_id'
    )
    quelyos_dynamic_stock_basis = fields.Selection([
        ('free', 'Quantité libre'),
        ('forecast', 'Prévisionnel'),
    ], string="Base de calcul du stock", config_parameter='quelyos_dynamic_picking.stock_basis')
    quelyos_dynamic_only_website = fields.Boolean(
        string="Appliquer uniquement eCommerce",
        config_parameter='quelyos_dynamic_picking.only_website'
    )
    quelyos_dynamic_shop_ids = fields.Many2many(
        'stock.location',
        string="Boutiques à considérer (ordre = priorité)",
        domain="[('usage', '=', 'internal')]",
        config_parameter='quelyos_dynamic_picking.shop_ids'
    )
