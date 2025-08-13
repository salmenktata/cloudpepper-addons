# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    quelyos_dynamic_enabled = fields.Boolean(
        string="Activer Picking Dynamique",
        default=True,
        help="Active la stratégie de sélection automatique de l'emplacement source."
    )

    quelyos_dynamic_only_website = fields.Boolean(
        string="Appliquer uniquement eCommerce",
        default=False,
        help="Si coché, la stratégie ne s'applique qu'aux commandes passées sur le site web."
    )

    quelyos_dynamic_central_location_id = fields.Many2one(
        'stock.location',
        string="Emplacement central (CENT/Stock)",
        help="Emplacement central prioritaire si son stock couvre toute la commande."
    )

    quelyos_dynamic_shop_ids = fields.Many2many(
        'stock.location',
        'company_quelyos_dynamic_shop_rel',  # nom de la table relationnelle
        'company_id',
        'location_id',
        string="Boutiques à considérer",
        help="Liste des boutiques à prendre en compte dans la stratégie. L'ordre défini ici est celui utilisé dans le critère 3."
    )

    quelyos_dynamic_stock_basis = fields.Selection(
        [
            ('free', 'Quantité libre'),
            ('forecast', 'Prévisionnel'),
        ],
        string="Type de stock utilisé",
        default='free',
        help="Type de stock utilisé pour évaluer les disponibilités."
    )
