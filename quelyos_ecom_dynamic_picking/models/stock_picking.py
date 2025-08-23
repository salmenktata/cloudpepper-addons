# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.model
    def quelyos_dynamic_pick(self, picking):
        """ Stratégie Quelyos – Dynamic Picking """
        company = picking.company_id
        param = company.quelyos_dynamic_enabled
        if not param or picking.picking_type_code != 'outgoing':
            return

        locations = company.quelyos_dynamic_locations.ids
        if not locations:
            return

        move_lines = picking.move_ids_without_package.filtered(lambda m: m.product_id.type == 'product')
        for move in move_lines:
            product = move.product_id
            qty_needed = move.product_uom_qty

            # Chercher si une seule boutique couvre tout
            candidate = None
            for loc in locations:
                qty_available = product.with_context(location=loc).qty_available
                if qty_available >= qty_needed:
                    candidate = loc
                    break

            if candidate:
                # Assigner tout depuis la boutique trouvée
                move.write({'location_id': candidate})
                picking.message_post(
                    body=_("Quelyos – Dynamic Picking: %s unités assignées depuis %s.") % (
                        qty_needed,
                        self.env['stock.location'].browse(candidate).display_name,
                    )
                )
            else:
                # Pas de boutique couvrant tout → on prend la boutique "préférée"
                candidate = locations[0]
                move.write({'location_id': candidate})

                # Création réassort interne si activé
                if company.quelyos_dynamic_auto_replenish and company.quelyos_dynamic_central_location_id:
                    central = company.quelyos_dynamic_central_location_id
                    self.env['stock.move'].create({
                        'name': _('Réassort Quelyos: %s') % product.display_name,
                        'product_id': product.id,
                        'product_uom_qty': qty_needed,
                        'product_uom': move.product_uom.id,
                        'location_id': central.id,
                        'location_dest_id': candidate,
                        'picking_id': picking.id,
                        'company_id': company.id,
                    })
                    picking.message_post(
                        body=_("Quelyos – Dynamic Picking: %s unités assignées depuis %s (réassort interne créé depuis %s).") % (
                            qty_needed,
                            self.env['stock.location'].browse(candidate).display_name,
                            central.display_name,
                        )
                    )
                else:
                    picking.message_post(
                        body=_("Quelyos – Dynamic Picking: %s unités assignées depuis %s (pas de réassort possible).") % (
                            qty_needed,
                            self.env['stock.location'].browse(candidate).display_name,
                        )
                    )
