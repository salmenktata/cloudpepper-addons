# -*- coding: utf-8 -*-
from odoo import api, fields, models
from collections import Counter

class StockPicking(models.Model):
    _inherit = "stock.picking"

    quelyos_log = fields.Text(string="Quelyos Log", readonly=True)

    def _quelyos_apply_auto_source_strategy(self):
        """Applique la stratégie automatique définie dans la configuration."""
        self.ensure_one()
        company = self.company_id
        log_lines = []

        if not company.quelyos_dynamic_enabled:
            log_lines.append("Picking dynamique désactivé.")
            self.quelyos_log = "\n".join(log_lines)
            return

        # Charger paramètres
        only_website = company.quelyos_dynamic_only_website
        central_location = company.quelyos_dynamic_central_location_id
        shop_locations = company.quelyos_dynamic_shop_ids  # Ordre défini par l'utilisateur
        stock_basis = company.quelyos_dynamic_stock_basis or 'free'

        # Déterminer si picking éligible
        if only_website and self.sale_id and not self.sale_id.website_id:
            log_lines.append("Commande hors site web - stratégie non appliquée.")
            self.quelyos_log = "\n".join(log_lines)
            return

        # Fonction pour obtenir le stock dispo d’un produit dans un emplacement
        def get_stock(product, location):
            qty = product.with_context(location=location.id)._compute_quantities_dict(
                lot_id=False, owner_id=False, package_id=False
            )[product.id]
            return qty.get(stock_basis + '_qty', 0.0)

        # Liste des lignes produit/qty
        order_lines = [(ml.product_id, ml.product_qty) for ml in self.move_ids_without_package]

        # =====================
        # CRITÈRE 1 : Central couvre tout
        # =====================
        if central_location:
            if all(get_stock(prod, central_location) >= qty for prod, qty in order_lines):
                for ml in self.move_ids_without_package:
                    ml.location_id = central_location
                log_lines.append(f"Critère 1 : Central '{central_location.display_name}' couvre tout → sélectionné.")
                self.quelyos_log = "\n".join(log_lines)
                return
            else:
                log_lines.append(f"Critère 1 non satisfait : Central ne couvre pas tout.")

        # =====================
        # CRITÈRE 2 : Boutique avec plus de stock cumulé
        # =====================
        if shop_locations:
            shop_totals = {}
            for shop in shop_locations:
                total_qty = sum(get_stock(prod, shop) for prod, _qty in order_lines)
                shop_totals[shop] = total_qty
            if shop_totals:
                best_shop = max(shop_totals, key=shop_totals.get)
                if shop_totals[best_shop] > 0:
                    for ml in self.move_ids_without_package:
                        ml.location_id = best_shop
                    log_lines.append(f"Critère 2 : Boutique '{best_shop.display_name}' avec le plus de stock → sélectionnée.")
                    self.quelyos_log = "\n".join(log_lines)
                    return
            log_lines.append("Critère 2 non satisfait.")

        # =====================
        # CRITÈRE 3 : Ordre défini par utilisateur
        # =====================
        for shop in shop_locations:
            if any(get_stock(prod, shop) > 0 for prod, _qty in order_lines):
                for ml in self.move_ids_without_package:
                    ml.location_id = shop
                log_lines.append(f"Critère 3 : Première boutique dans l’ordre ({shop.display_name}) ayant du stock → sélectionnée.")
                self.quelyos_log = "\n".join(log_lines)
                return
        log_lines.append("Critère 3 non satisfait.")

        # =====================
        # CRITÈRE 4 : Réassort vers magasin avec le plus d’articles déjà dans commande
        # =====================
        shop_article_count = Counter()
        for shop in shop_locations:
            count = sum(1 for prod, _qty in order_lines if get_stock(prod, shop) > 0)
            shop_article_count[shop] = count
        if shop_article_count:
            best_shop = max(shop_article_count, key=shop_article_count.get)
            for ml in self.move_ids_without_package:
                ml.location_id = best_shop
            log_lines.append(f"Critère 4 : Réassort vers '{best_shop.display_name}' (plus d’articles présents).")
            self.quelyos_log = "\n".join(log_lines)
            return

        log_lines.append("Aucun critère satisfait – pas de changement de source.")
        self.quelyos_log = "\n".join(log_lines)

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        rec._quelyos_apply_auto_source_strategy()
        return rec

    def write(self, vals):
        res = super().write(vals)
        if 'move_ids_without_package' in vals or 'location_id' in vals:
            for rec in self:
                rec._quelyos_apply_auto_source_strategy()
        return res
