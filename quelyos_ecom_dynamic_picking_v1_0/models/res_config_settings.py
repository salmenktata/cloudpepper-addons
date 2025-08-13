# -*- coding: utf-8 -*-
from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # --- Activation globale ---
    quelyos_dynamic_enabled = fields.Boolean(
        string="Activer le picking dynamique",
        help="exp : active la sélection automatique de l’emplacement source pour les livraisons sortantes.",
        related="company_id.quelyos_dynamic_enabled",
        readonly=False,
    )

    # --- Portée ---
    quelyos_dynamic_only_website = fields.Boolean(
        string="Appliquer uniquement aux commandes eCommerce",
        help="exp : si coché, n’applique la stratégie que pour les commandes issues du site web.",
        related="company_id.quelyos_dynamic_only_website",
        readonly=False,
    )

    # --- Emplacement central ---
    quelyos_dynamic_central_location_id = fields.Many2one(
        'stock.location',
        string="Emplacement central (CENT/Stock)",
        help="exp : emplacement prioritaire si son stock couvre toute la commande.",
        related="company_id.quelyos_dynamic_central_location_id",
        readonly=False,
    )

    # --- Boutiques concernées (ordre = ordre de sélection en Critère 3) ---
    quelyos_dynamic_shop_ids = fields.Many2many(
        'stock.location',
        string="Boutiques à considérer (ordre = Critère 3)",
        help="exp : liste des boutiques prises en compte ; l’ordre d’ajout est utilisé pour le Critère 3.",
        related="company_id.quelyos_dynamic_shop_ids",
        readonly=False,
    )

    # --- Base de stock utilisée pour les calculs ---
    quelyos_dynamic_stock_basis = fields.Selection(
        [
            ('free', 'Quantité libre (physique - réservé)'),
            ('forecast', 'Prévisionnel (inclut entrées futures)'),
        ],
        string="Type de stock utilisé",
        help="exp : détermine comment on calcule les disponibilités pour les critères 1 et 2.",
        related="company_id.quelyos_dynamic_stock_basis",
        readonly=False,
    )
