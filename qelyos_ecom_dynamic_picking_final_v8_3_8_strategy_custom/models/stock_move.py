from odoo import models

class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_assign(self):
        ICP = self.env['ir.config_parameter'].sudo()
        if not ICP.get_param('ecom_dynamic_enabled', 'False') == 'True':
            return super()._action_assign()

        strategy = ICP.get_param('ecom_dynamic_strategy', 'qelyos_custom')
        free_stock_only = ICP.get_param('ecom_dynamic_free_stock_only', 'True') == 'True'

        if strategy != 'qelyos_custom':
            return super()._action_assign()

        for move in self:
            order = move.picking_id.sale_id
            if not order:
                continue

            # Locations
            central_loc = self.env['stock.location'].search([('complete_name', '=', 'CENT/Stock')], limit=1)
            boutiques = self.env['stock.location'].search([('complete_name', 'like', 'Boutique')])

            # Get quantity available function
            def get_free_qty(product, location):
                qty = product.with_context(location=location.id).free_qty if free_stock_only else product.with_context(location=location.id).qty_available
                return qty

            # 1️⃣ CENT covers all
            if all(get_free_qty(l.product_id, central_loc) >= l.product_uom_qty for l in order.order_line):
                move.picking_id.location_id = central_loc
                continue

            # 2️⃣ Max available among boutiques
            max_boutique = None
            max_qty_total = 0
            for b in boutiques:
                total_b = sum(get_free_qty(l.product_id, b) for l in order.order_line)
                if total_b > max_qty_total:
                    max_qty_total = total_b
                    max_boutique = b

            # 3️⃣ Order strict: Gafsa → Sousse → Soukra
            for shop_name in ['Boutique Gafsa/Stock', 'Boutique Sousse/Stock', 'Boutique Soukra/Stock']:
                shop = self.env['stock.location'].search([('complete_name', '=', shop_name)], limit=1)
                if shop and all(get_free_qty(l.product_id, shop) >= l.product_uom_qty for l in order.order_line):
                    move.picking_id.location_id = shop
                    break
            else:
                # 4️⃣ No full coverage → take max boutique & trigger internal transfer
                if max_boutique:
                    move.picking_id.location_id = max_boutique
                    # TODO: Add internal transfer trigger here if needed
        return super()._action_assign()
