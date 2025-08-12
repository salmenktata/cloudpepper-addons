# -*- coding: utf-8 -*-
from odoo import models, api

class SaleOrder(models.Model):
    _inherit = "sale.order"

    # ---- Helpers ----
    @api.model
    def _get_available_qty(self, product, location):
        return self.env['stock.quant']._get_available_quantity(product, location)

    def _score_location_for_picking(self, picking, loc):
        if not picking.move_ids_without_package:
            return 0.0
        return min(self._get_available_qty(m.product_id, loc) for m in picking.move_ids_without_package)

    def _apply_source_location(self, picking, chosen_loc, reason, debug_html=None):
        old_src = picking.location_id.display_name if picking.location_id else "N/A"
        picking.location_id = chosen_loc.id
        for move in picking.move_ids_without_package:
            move.location_id = chosen_loc.id
        try:
            picking.action_assign()
        except Exception:
            picking.action_unreserve()
            picking.action_assign()
        body = f"Source forcée: {old_src} → <b>{chosen_loc.display_name}</b><br/>{reason}"
        if debug_html:
            body += "<br/>" + debug_html
        picking.message_post(body=body)

    def _find_internal_picking_type(self, source_loc_id, dest_loc_id):
        return self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('default_location_src_id', '=', source_loc_id),
            ('default_location_dest_id', '=', dest_loc_id)
        ], limit=1)

    def _create_internal_transfer(self, dest_location, moves):
        StockPicking = self.env['stock.picking']
        for move in moves:
            quant = self.env['stock.quant'].search([
                ('product_id', '=', move.product_id.id),
                ('quantity', '>=', move.product_uom_qty)
            ], limit=1)
            source_loc = quant.location_id
            if not source_loc or source_loc == dest_location:
                continue
            picking_type = self._find_internal_picking_type(source_loc.id, dest_location.id)
            if not picking_type:
                continue
            StockPicking.create({
                'picking_type_id': picking_type.id,
                'location_id': source_loc.id,
                'location_dest_id': dest_location.id,
                'move_ids_without_package': [(0, 0, {
                    'name': move.product_id.display_name,
                    'product_id': move.product_id.id,
                    'product_uom_qty': move.product_uom_qty,
                    'product_uom': move.product_uom.id,
                    'location_id': source_loc.id,
                    'location_dest_id': dest_location.id,
                })]
            })

    def _warehouse_key_locs(self, picking):
        wh = picking.picking_type_id.warehouse_id or self.env['stock.warehouse'].search([('company_id','=',picking.company_id.id)], limit=1)
        return {'stock': wh.lot_stock_id} if wh else {}

    def _classify_delivery_step(self, picking):
        if picking.picking_type_code == 'outgoing':
            return 'outgoing'
        if picking.picking_type_code == 'internal':
            # We don't need full classification here; we always target PICK when exists
            return 'internal'
        return None

    def _format_debug_table(self, picking, locations):
        lines = picking.move_ids_without_package
        header = ['Emplacement'] + [m.product_id.display_name for m in lines] + ['score(min)']
        rows = []
        for loc in locations:
            row = [loc.display_name]
            for m in lines:
                row.append(str(self._get_available_qty(m.product_id, loc)))
            row.append(str(self._score_location_for_picking(picking, loc)))
            rows.append(row)
        html = '<table border="1" cellpadding="3" cellspacing="0"><tr>' + ''.join(f'<th>{h}</th>' for h in header) + '</tr>'
        for r in rows:
            html += '<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>'
        html += '</table>'
        return html

    def _choose_location_v8(self, company, picking):
        locations_all = company.ecom_dynamic_source_location_ids.filtered(lambda l: l.usage == 'internal')
        if not locations_all:
            return None, "", ""
        lines = picking.move_ids_without_package
        wh_stock = self._warehouse_key_locs(picking).get('stock')
        # Separate CENTRAL and boutiques
        central = wh_stock if wh_stock and wh_stock in locations_all else locations_all.filtered(lambda l: 'CENT' in (l.complete_name or l.display_name or '').upper() or 'CENTRAL' in (l.complete_name or l.display_name or '').upper())[:1]
        central = central and (central if isinstance(central, models.Model) else central[0]) or False
        boutiques = [l for l in locations_all if l != central]

        # Build debug
        debug_html = self._format_debug_table(picking, [loc for loc in [central] if loc] + boutiques)

        # Critère 1: CENTRAL disponible pour toutes les lignes
        if central and all(self._get_available_qty(m.product_id, central) >= m.product_uom_qty for m in lines):
            return central, "Critère 1 (DISPONIBLE): CENTRAL couvre toute la commande", debug_html

        # Critère 2: Max disponible parmi TOUTES les boutiques listées
        if boutiques:
            scores = [(loc, self._score_location_for_picking(picking, loc)) for loc in boutiques]
            best = max(scores, key=lambda x: x[1]) if scores else (None, 0)
            if best[0] and best[1] > 0:
                return best[0], f"Critère 2: Max dispo boutiques → {best[0].display_name} (score={best[1]})", debug_html

        # Critère 3: Ordre strict GAFSA > SOUSSE > SOUKRA (choisir le premier qui couvre; sinon réassort)
        order_names = ['GAFSA','SOUSE','SOUKRA']
        ordered = []
        for nm in order_names:
            l = next((x for x in boutiques if nm in (x.complete_name or x.display_name or '').upper()), None)
            if l:
                ordered.append(l)
        # Add any remaining boutiques not matched, to be safe
        ordered += [l for l in boutiques if l not in ordered]

        for loc in ordered:
            if all(self._get_available_qty(m.product_id, loc) >= m.product_uom_qty for m in lines):
                return loc, f"Critère 3: Ordre strict → {loc.display_name}", debug_html

        # Aucune boutique ne couvre => réassort interne sur la 1ère de l'ordre (ou la première de la liste si vide)
        dest = ordered[0] if ordered else (boutiques[0] if boutiques else (central or locations_all[0]))
        return dest, f"Critère 3: Aucune dispo → Réassort interne vers {dest.display_name}", debug_html

    def _action_confirm(self):
        res = super()._action_confirm()
        for order in self:
            company = order.company_id
            website_limit = company.ecom_dynamic_website_id
            if not order.website_id or (website_limit and order.website_id != website_limit):
                continue

            pickings = order.picking_ids
            if not pickings:
                continue

            # Target: if internal picking exists (2/3 steps), use it; else outgoing (1 step)
            target = pickings.filtered(lambda p: p.picking_type_code == 'internal')[:1] or pickings.filtered(lambda p: p.picking_type_code == 'outgoing')[:1]
            if not target:
                continue

            for picking in target:
                strategy = company.ecom_dynamic_strategy
                if strategy != 'central_then_max_then_order_strict':
                    # Optional: handle other strategies exactly as before (not implemented in v8 focus)
                    continue
                chosen_loc, reason, debug_html = self._choose_location_v8(company, picking)
                if not chosen_loc:
                    continue
                # If chosen_loc doesn't fully cover, create internal transfer THEN apply
                fully = all(self._get_available_qty(m.product_id, chosen_loc) >= m.product_uom_qty for m in picking.move_ids_without_package)
                if not fully:
                    self._create_internal_transfer(chosen_loc, picking.move_ids_without_package)
                    reason += " | Réassort interne créé (couverture incomplète)."
                self._apply_source_location(picking, chosen_loc, reason, debug_html=debug_html)
        return res
