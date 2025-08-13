# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.model
    def _quelyos_log_event(self, action, extra=None):
        # Journalisation interne (désactivable si inutile)
        _logger = self.env['ir.logging']
        _logger.create({
            'name': 'Quelyos Dynamic Picking',
            'type': 'server',
            'dbname': self._cr.dbname,
            'level': 'info',
            'message': f"Action {action} sur {self.name} - {extra}",
            'path': 'quelyos_ecom_dynamic_picking',
            'func': '_quelyos_log_event',
            'line': '0',
        })

    def action_assign(self):
        res = super().action_assign()
        for rec in self:
            rec._quelyos_apply_auto_source_strategy()
        return res

    def _quelyos_apply_auto_source_strategy(self):
        ICP = self.env['ir.config_parameter'].sudo()
        strategy = ICP.get_param('quelyos_dynamic_strategy', 'custom')
        only_website = ICP.get_param('quelyos_dynamic_only_website', 'False') == 'True'
        central_location_id = int(ICP.get_param('quelyos_dynamic_central_location_id', '0')) or False

        for picking in self:
            if strategy != 'custom':
                continue

            if only_website and picking.sale_id and not picking.sale_id.website_id:
                continue

            for move in picking.move_ids_without_package:
                product = move.product_id
                qty_needed = move.product_uom_qty

                # -------------------------
                # Critère 1 : Emplacement central
                # -------------------------
                candidate_location = None
                if central_location_id:
                    qty_central = self._get_available_qty(product, central_location_id)
                    if qty_central >= qty_needed:
                        candidate_location = self.env['stock.location'].browse(central_location_id)

                # -------------------------
                # Critère 2 : Plus grande quantité disponible
                # -------------------------
                if not candidate_location:
                    location_qties = self._get_all_location_quantities(product)
                    if location_qties:
                        candidate_location = max(location_qties, key=lambda x: x[1])[0]

                # -------------------------
                # Critère 3 : Plus proche de 0 stock restant
                # -------------------------
                if not candidate_location:
                    location_qties = self._get_all_location_quantities(product)
                    if location_qties:
                        candidate_location = min(location_qties, key=lambda x: x[1])[0]

                # -------------------------
                # Critère 4 : Réassort vers magasin le plus fourni en articles de la commande
                # -------------------------
                if not candidate_location:
                    candidate_location = self._get_location_with_most_items_in_order(picking)

                if candidate_location:
                    move.location_id = candidate_location
                    self._quelyos_log_event("auto_assign_location", {
                        'product': product.display_name,
                        'location': candidate_location.display_name,
                        'qty': qty_needed
                    })

    def _get_available_qty(self, product, location_id):
        return sum(self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id', '=', location_id)
        ]).mapped('quantity'))

    def _get_all_location_quantities(self, product):
        quants = self.env['stock.quant'].search([
            ('product_id', '=', product.id)
        ])
        location_qties = {}
        for q in quants:
            location_qties[q.location_id] = location_qties.get(q.location_id, 0) + q.quantity
        return [(loc, qty) for loc, qty in location_qties.items()]

    def _get_location_with_most_items_in_order(self, picking):
        item_counts = {}
        for move in picking.move_ids_without_package:
            quants = self.env['stock.quant'].search([
                ('product_id', '=', move.product_id.id)
            ])
            for q in quants:
                item_counts[q.location_id] = item_counts.get(q.location_id, 0) + q.quantity
        if not item_counts:
            return None
        return max(item_counts.items(), key=lambda x: x[1])[0]
