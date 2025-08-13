# -*- coding: utf-8 -*-
from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    quelyos_dynamic_enabled = fields.Boolean(
        string="Activer le picking dynamique",
        default=False,
        help="Active la sélection automatique de l’emplacement source pour les livraisons sortantes."
    )

    quelyos_dynamic_only_website = fields.Boolean(
        string="Appliquer uniquement aux commandes eCommerce",
        default=False,
        help="Si coché, n’applique la stratégie que pour les commandes issues du site web."
    )

    quelyos_dynamic_central_location_id = fields.Many2one(
        'stock.location',
        string="Emplacement central (CENT/Stock)",
        help="Emplacement prioritaire si son stock couvre toute la commande."
    )

    quelyos_dynamic_shop_ids = fields.Many2many(
        'stock.location',
        'company_quelyos_dynamic_shop_rel',  # nom de table relationnelle
        'company_id', 'location_id',
        string="Boutiques à considérer (ordre Critère 3)",
        help="Liste des boutiques prises en compte ; l’ordre d’ajout est utilisé pour le Critère 3."
    )

    quelyos_dynamic_stock_basis = fields.Selection(
        [
            ('free', 'Quantité libre (physique - réservé)'),
            ('forecast', 'Prévisionnel (inclut entrées futures)'),
        ],
        string="Type de stock utilisé",
        default='free',
        help="Détermine comment on calcule les disponibilités pour les critères 1 et 2."
    )
