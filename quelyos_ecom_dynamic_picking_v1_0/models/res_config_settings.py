# -*- coding: utf-8 -*-
from odoo import models, fields


# ---------------------------------------------------------------------------
# Extension de la société : stockage des paramètres par société
# ---------------------------------------------------------------------------
class ResCompany(models.Model):
    _inherit = "res.company"

    quelyos_dynamic_enabled = fields.Boolean(
        string="Activer le picking dynamique",
        help="exp : active la logique de sélection automatique de l’emplacement source "
             "et le réassort interne si nécessaire."
    )

    quelyos_dynamic_strategy = fields.Selection(
        [
            ("custom", "Critères personnalisés"),
            ("disabled", "Désactivé"),
        ],
        string="Stratégie appliquée",
        default="custom",
        help="exp : « Critères personnalisés » = 1) CENT/Stock si tout couvert, "
             "2) meilleure boutique (stock cumulé max), 3) boutiques dans l’ordre défini."
    )

    quelyos_dynamic_stock_basis = fields.Selection(
        [
            ("free", "Quantité libre"),
            ("onhand", "Physique (On‑Hand)"),
            ("forecast", "Prévisionnel"),
        ],
        string="Type de stock utilisé",
        default="free",
        help="exp : "
             "• Quantité libre = stock physique − réservations\n"
             "• Physique (On‑Hand) = stock physique sans tenir compte des réservations\n"
             "• Prévisionnel = inclut les entrées/sorties à venir"
    )

    quelyos_dynamic_only_website = fields.Boolean(
        string="Appliquer uniquement aux commandes eCommerce",
        help="exp : si coché, la stratégie ne s’applique qu’aux commandes passées via le site web."
    )

    quelyos_dynamic_central_location_id = fields.Many2one(
        "stock.location",
        string="Emplacement central (CENT/Stock)",
        help="exp : emplacement prioritaire si son stock couvre la commande."
    )

    quelyos_dynamic_shop_ids = fields.Many2many(
        "stock.location",
        "res_company_quelyos_shop_rel",    # table relation explicite
        "company_id",                      # colonne vers res.company
        "location_id",                     # colonne vers stock.location
        string="Boutiques concernées (ordre pris en compte)",
        help="exp : sélectionne les boutiques à prendre en compte. "
             "L’ordre d’ajout est utilisé pour le critère 3."
    )


# ---------------------------------------------------------------------------
# Paramètres système : expose les champs société dans l'UI (onglet Ventes)
# ---------------------------------------------------------------------------
class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Activation
    quelyos_dynamic_enabled = fields.Boolean(
        related="company_id.quelyos_dynamic_enabled",
        readonly=False
    )

    # Stratégie
    quelyos_dynamic_strategy = fields.Selection(
        [
            ("custom", "Critères personnalisés"),
            ("disabled", "Désactivé"),
        ],
        related="company_id.quelyos_dynamic_strategy",
        readonly=False
    )

    # Base de stock
    quelyos_dynamic_stock_basis = fields.Selection(
        [
            ("free", "Quantité libre"),
            ("onhand", "Physique (On‑Hand)"),
            ("forecast", "Prévisionnel"),
        ],
        related="company_id.quelyos_dynamic_stock_basis",
        readonly=False
    )

    # Portée eCommerce
    quelyos_dynamic_only_website = fields.Boolean(
        related="company_id.quelyos_dynamic_only_website",
        readonly=False
    )

    # Emplacement central
    quelyos_dynamic_central_location_id = fields.Many2one(
        "stock.location",
        related="company_id.quelyos_dynamic_central_location_id",
        readonly=False
    )

    # Boutiques (ordre = ordre d’ajout par l’utilisateur)
    quelyos_dynamic_shop_ids = fields.Many2many(
        comodel_name="stock.location",
        relation="res_company_quelyos_shop_rel",  # même table de relation que sur la société
        column1="company_id",
        column2="location_id",
        related="company_id.quelyos_dynamic_shop_ids",
        readonly=False
    )
