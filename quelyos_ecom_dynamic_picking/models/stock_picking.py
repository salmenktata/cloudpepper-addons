# -*- coding: utf-8 -*-
import logging
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    quelyos_log = fields.Text(string="Quelyos – Journal (local)")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Traitement optimisé en masse des pickings sortants.
        # Nous allons traiter les pickings par la suite pour éviter les divisions.
        return records

    def action_assign(self):
        res = super().action_assign()
        for rec in self:
            reserved_flag = any(m.state in ('assigned', 'partially_available') for m in rec.move_ids_without_package)
            reserved_qty = sum(rec.move_line_ids.mapped('reserved_qty'))
            _logger.info(
                "[QUELYOS][assign] Vérification disponibilité pour %s: réservé=%s, quantité réservée=%s",
                rec.name, reserved_flag, reserved_qty
            )
        return res

    def button_validate(self):
        if self.env["ir.config_parameter"].sudo().get_param("quelyos_dynamic_strict_order_enabled", 'False') in ('1', 'True', 'true'):
            for picking in self:
                picking._quelyos_check_strict_order_before_validate()
        res = super().button_validate()
        for rec in self:
            _logger.info("[QUELYOS][validate] Validation picking %s, état final: %s", rec.name, rec.state)
        return res

    def _quelyos_apply_auto_source_strategy(self):
        """
        Applique la stratégie de sélection de l'emplacement source pour les livraisons sortantes
        de manière optimisée et rapide, sans verrouillage de la base de données.
        """
        # Récupération des paramètres en dehors de la boucle
        P = self.env["ir.config_parameter"].sudo()

        def _get_param(key, default=None):
            return P.get_param(f"quelyos_dynamic_{key}", default)

        strategy = _get_param("strategy", "custom")
        if strategy != "custom":
            return

        only_web = _get_param("only_website", 'False') in ('1', 'True', 'true')
        basis = _get_param("stock_basis", "free")
        central_id = int(_get_param("central_location_id", '0') or '0')
        shop_ids_csv = _get_param("shop_ids", "")
        strict_names_enabled = _get_param("strict_order_enabled", 'False') in ('1', 'True', 'true')
        order_names = _get_param("shop_order_names", "") or ""

        priority_names = [n.strip().lower() for n in order_names.replace(">", ",").split(",") if n.strip()]
        shops_ids = [int(x) for x in shop_ids_csv.split(",") if x]

        Loc = self.env["stock.location"].sudo()
        central = Loc.browse(central_id) if central_id else self.env['stock.location'].sudo()
        shops = Loc.browse(shops_ids)
        all_locs = central + shops

        if not all_locs:
            self._log_event(self, "skip", {"exp": "Aucun emplacement central ni boutique configuré"})
            return

        # ----------- PATCH PoS ROBUSTE -----------
        # Exclure les pickings issus du PoS sans supposer l'existence d'un champ custom sur sale.order.
        # - On pré-collecte les sale.order liés
        sale_ids = set(self.mapped('sale_id').ids)
        sale_ids_with_pos = set()

        # Ne plante pas si le module PoS n'est pas installé
        if sale_ids and ('pos.order' in self.env):
            pos_orders = self.env['pos.order'].sudo().search([('sale_order_ids', 'in', list(sale_ids))])
            # pos.order.sale_order_ids est une M2M -> on récupère tous les sale_id liés à un pos.order
            sale_ids_with_pos = set(pos_orders.mapped('sale_order_ids').ids)

        pickings_to_process = self.filtered(lambda p: not p.sale_id or p.sale_id.id not in sale_ids_with_pos)
        # --------- FIN PATCH PoS ROBUSTE ---------

        # Optimisation : Préchargement des données pour toutes les commandes
        all_products = pickings_to_process.move_ids_without_package.product_id
        all_product_ids = all_products.ids

        stock_data = self._get_available_quantities(all_product_ids, all_locs.ids, basis)

        final_sources = {}
        replenish_data = defaultdict(list)

        for picking in pickings_to_process:
            if not picking.picking_type_id or picking.picking_type_id.code != "outgoing":
                continue
            if only_web and not (picking.sale_id and getattr(picking.sale_id, "website_id", False)):
                continue

            self._log_event(picking, "start_strategy", {"exp": "Début de la stratégie de sélection de la source"})

            req = {
                move.product_id.id: move.product_uom._compute_quantity(move.product_uom_qty, move.product_id.uom_id)
                for move in picking.move_ids_without_package
            }

            if not req:
                self._log_event(picking, "no_moves", {"exp": "Aucun mouvement de stock, skip"})
                continue

            def check_full_coverage(location):
                return all(stock_data.get(location.id, {}).get(pid, 0.0) >= need for pid, need in req.items())

            final_source = self.env['stock.location']
            strategie_appliquee = ""

            # Début de la logique de sélection
            central_ok = check_full_coverage(central) if central else False
            if central_ok:
                final_source = central
                strategie_appliquee = "central_complet"
            else:
                best_shop = self.env['stock.location']
                if strict_names_enabled and priority_names:
                    for name in priority_names:
                        shop = shops.filtered(lambda l: l.name.strip().lower() == name)
                        if shop and check_full_coverage(shop):
                            best_shop = shop
                            break
                if not best_shop:
                    best_score = -1.0
                    best_tiebreak = -1.0
                    for shop in shops:
                        free_sum, cover_sum = 0.0, 0.0
                        for pid, need in req.items():
                            have = stock_data.get(shop.id, {}).get(pid, 0.0)
                            free_sum += have
                            cover_sum += max(0.0, min(have, need))
                        if (free_sum > best_score) or (free_sum == best_score and cover_sum > best_tiebreak):
                            best_score = free_sum
                            best_tiebreak = cover_sum
                            best_shop = shop

                if best_shop and check_full_coverage(best_shop):
                    final_source = best_shop
                    strategie_appliquee = "meilleure_boutique_ou_ordre_strict_complet"
                else:
                    best_coverage_loc = self.env['stock.location']
                    best_coverage_score = -1.0
                    for loc in all_locs:
                        if not loc:
                            continue
                        current_coverage_score = sum(
                            min(stock_data.get(loc.id, {}).get(pid, 0.0), need) for pid, need in req.items()
                        )
                        if current_coverage_score > best_coverage_score:
                            best_coverage_score = current_coverage_score
                            best_coverage_loc = loc

                    if best_coverage_loc:
                        final_source = best_coverage_loc
                        strategie_appliquee = "meilleure_couverture"
                    else:
                        final_source = central or (shops and shops[:1])
                        strategie_appliquee = "fallback"

            if not final_source:
                self._log_event(picking, "fail", {"exp": "Impossible de déterminer une source"})
                continue

            final_sources[picking.id] = final_source.id

            # Préparation de réassort interne si la source n'est pas le central
            if final_source and central and final_source.id != central.id:
                for pid, need in req.items():
                    have = stock_data.get(final_source.id, {}).get(pid, 0.0)
                    missing = max(0.0, need - have)
                    if missing > 0:
                        prod = self.env["product.product"].browse(pid)
                        replenish_data[picking.id].append({
                            "name": f"{central.display_name} -> {final_source.display_name} : {prod.display_name}",
                            "product_id": prod.id,
                            "product_uom": prod.uom_id.id,
                            "product_uom_qty": missing,
                            "location_id": central.id,
                            "location_dest_id": final_source.id,
                        })

            # Appliquer la source au picking et à ses moves
            picking.location_id = final_source.id
            picking.move_ids_without_package.write({"location_id": final_source.id})

            self._log_event(picking, "auto_source_result", {
                "exp": "Sélection source automatique",
                "choisie": final_source.display_name if final_source else False,
                "strategie": strategie_appliquee,
                "reassort_cree": len(replenish_data[picking.id]) > 0,
            })
            body = _(
                "📦 Stratégie Quelyos : source '%(src)s' (règle : %(rule)s).%(reassort)s",
                src=final_source.display_name,
                rule=strategie_appliquee.replace('_', ' ').capitalize(),
                reassort=" Réassort créé." if len(replenish_data[picking.id]) > 0 else ""
            )
            picking.message_post(body=body)

        # Création des réassorts internes nécessaires
        if replenish_data:
            for picking_id, moves_data in replenish_data.items():
                picking_record = self.browse(picking_id)
                picking_type_internal = self.env["stock.picking.type"].sudo().search([
                    ("code", "=", "internal"),
                    ("warehouse_id", "=", picking_record.picking_type_id.warehouse_id.id)
                ], limit=1) or self.env["stock.picking.type"].sudo().search([("code", "=", "internal")], limit=1)

                self.env["stock.picking"].sudo().create({
                    "picking_type_id": picking_type_internal.id if picking_type_internal else False,
                    "location_id": central.id,
                    "location_dest_id": picking_record.location_id.id,
                    "origin": f"{picking_record.name or picking_record.origin or ''} / Réassort auto",
                    "move_ids_without_package": moves_data,
                })

        # Réservation automatique
        try:
            self.action_assign()
            self._log_event(self, "assign", {"exp": "Réservation automatique réussie pour le recordset"})
        except Exception as e:
            self._log_event(self, "assign_error", {"exp": "Erreur à la réservation auto pour le recordset", "erreur": str(e)})

    def _get_available_quantities(self, product_ids, location_ids, basis):
        """
        Optimisation: Récupère les stocks disponibles pour tous les produits et emplacements en une seule requête.
        Retourne un dictionnaire {location_id: {product_id: qty, ...}, ...}.
        """
        res = defaultdict(lambda: defaultdict(float))
        if not product_ids or not location_ids:
            return res

        if basis == "free":
            quants = self.env["stock.quant"].sudo().read_group(
                domain=[("product_id", "in", product_ids), ("location_id", "child_of", location_ids)],
                fields=["quantity:sum", "reserved_quantity:sum", "location_id", "product_id"],
                groupby=["location_id", "product_id"],
            )
            for quant in quants:
                # Vérification des clés
                if 'product_id' in quant and 'location_id' in quant:
                    loc_id = quant['location_id'][0]
                    prod_id = quant['product_id'][0]
                    available_qty = quant.get('quantity', 0.0) - quant.get('reserved_quantity', 0.0)
                    res[loc_id][prod_id] = max(0.0, available_qty)
        else:
            # Cette boucle est un goulot d'étranglement de performance et devrait être refactorisée si besoin
            for loc_id in location_ids:
                if not loc_id:
                    continue
                loc_ctx = self.env['stock.location'].browse(loc_id).with_context(compute_child=True)
                for product in self.env['product.product'].browse(product_ids):
                    prod_ctx = product.with_context(location=loc_ctx.id)
                    if basis == "onhand":
                        res[loc_id][product.id] = prod_ctx.qty_available
                    elif basis == "forecast":
                        res[loc_id][product.id] = prod_ctx.virtual_available
        return res

    def _log_event(self, record, event, extra=None):
        msg = f"[QUELYOS][{event.upper()}] {extra or {}}"
        record.quelyos_log = (record.quelyos_log or "") + ("\n" if record.quelyos_log else "") + msg
        _logger.info(msg)

    def _quelyos_check_strict_order_before_validate(self):
        self.ensure_one()
        P = self.env["ir.config_parameter"].sudo()
        strict_names_enabled = P.get_param("quelyos_dynamic_strict_order_enabled", 'False') in ('1', 'True', 'true')

        if not strict_names_enabled:
            return

        domain = [("id", "!=", self.id), ("state", "not in", ("done", "cancel"))]
        if self.group_id:
            domain += [("group_id", "=", self.group_id.id)]
        else:
            domain += [("origin", "=", self.origin)]

        blockers = self.env['stock.picking'].search(domain, limit=1)

        if blockers:
            raise UserError(_("Ordre strict : vous devez d'abord terminer '%s' (type : %s).")
                            % (blockers.display_name, blockers.picking_type_id.display_name))


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_confirm(self):
        res = super()._action_confirm()
        pickings = self.mapped("picking_ids").filtered(lambda p: p.picking_type_id.code == "outgoing")
        pickings._quelyos_apply_auto_source_strategy()
        return res
