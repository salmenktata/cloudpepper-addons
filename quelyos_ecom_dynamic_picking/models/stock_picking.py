# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # --------- Helpers quantités par base de stock ---------
    def _qy_get_qty_by_basis(self, product, location, basis):
        """Retourne une quantité numérique selon la base choisie."""
        Quant = self.env['stock.quant']
        if basis == "free":
            # quantité libre (réservable) stricte sur l'emplacement
            return Quant._get_available_quantity(product, location, strict=True)
        elif basis == "onhand":
            # physique (quantity) stricte sur l'emplacement
            quants = Quant.search([('product_id', '=', product.id), ('location_id', '=', location.id)])
            return sum(quants.mapped('quantity'))
        else:  # forecast
            # prévisionnel: via le context location → virtual_available
            return product.with_context(location=location.id).virtual_available

    def _qy_parse_strict_order(self, company, locations):
        """Renvoie la liste ordonnée d'IDs d'emplacements selon l'ordre strict défini, sinon l'ordre courant."""
        if not company.quelyos_dynamic_strict_order_enabled or not company.quelyos_dynamic_strict_shop_order:
            return locations.ids
        name_to_id = {loc.display_name.strip().lower(): loc.id for loc in locations}
        order_names = [x.strip().lower() for x in company.quelyos_dynamic_strict_shop_order.split(">") if x.strip()]
        ordered_ids = []
        for nm in order_names:
            loc_id = name_to_id.get(nm)
            if loc_id and loc_id in locations.ids and loc_id not in ordered_ids:
                ordered_ids.append(loc_id)
        for loc in locations:
            if loc.id not in ordered_ids:
