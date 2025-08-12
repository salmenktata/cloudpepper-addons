# -*- coding: utf-8 -*-
from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Stratégie appliquée
    quelyos_dynamic_strategy = fields.Selection(
        selection=[
            ('custom', 'Critères personnalisés'),
            ('disabled', 'Désactivé')
        ],
        string="Stratégie appliquée",
        help="Détermine la logique utilisée pour choisir l’emplacement source.\n"
             "• Critères personnalisés : applique la logique décrite (CENT complet, sinon meilleure boutique, sinon réassort).\n"
             "• Désactivé : aucune sélection automatique.",
        default='custom',
        config_parameter="quelyos_ecom_dynamic_picking.strategy"
    )

    # Type de calcul de stock
    quelyos_dynamic_stock_basis = fields.Selection(
        selection=[
            ('free', 'Quantité libre'),
            ('onhand', 'Quantité en stock physique'),
            ('forecast', 'Stock prévisionnel')
        ],
        string="Type de stock utilisé",
        help="Définit comment calculer les disponibilités :\n"
             "• Quantité libre : stock physique moins les réservations.\n"
             "• Quantité en stock physique : uniquement le stock réel, sans tenir compte des réservations.\n"
             "• Stock prévisionnel : inclut les entrées à venir.",
        default='free',
        config_parameter="quelyos_ecom_dynamic_picking.stock_basis"
    )

    # Application uniquement aux commandes eCommerce
    quelyos_dynamic_only_website = fields.Boolean(
        string="Appliquer uniquement aux commandes eCommerce",
        help="Si coché, la stratégie automatique ne s’applique qu’aux commandes passées via le site web.",
        default=False,
        config_parameter="quelyos_ecom_dynamic_picking.only_website"
    )

    # Emplacement central
    quelyos_dynamic_central_location_id = fields.Many2one(
        'stock.location',
        string="Emplacement central (CENT/Stock)",
        help="Sélectionnez l’emplacement de l’entrepôt central (ex : CENT/Stock).\n"
             "Cet emplacement sera prioritaire si son stock couvre toute la commande.",
        config_parameter="quelyos_ecom_dynamic_picking.central_location_id"
    )

    # Boutiques à inclure dans le calcul
    quelyos_dynamic_shop_ids = fields.Many2many(
        'stock.location',
        string="Boutiques à considérer",
        help="Liste des emplacements des boutiques à inclure dans le calcul de disponibilité.\n"
             "Ex : Gafsa/Stock, Sousse/Stock, Soukra/Stock.",
        config_parameter="quelyos_ecom_dynamic_picking.shop_ids"
    )

    # Activer/désactiver l’ordre strict
    quelyos_dynamic_strict_order_enabled = fields.Boolean(
        string="Activer l’ordre strict",
        help="Si activé, les boutiques sont testées dans l’ordre défini ci-dessous (ex : Gafsa → Sousse → Soukra) "
             "et la première qui couvre toute la commande est choisie.",
        default=False,
        config_parameter="quelyos_ecom_dynamic_picking.strict_shop_order_enabled"
    )

    # Ordre strict des boutiques
    quelyos_dynamic_shop_order_names = fields.Char(
        string="Ordre strict des boutiques",
        help="Saisissez les noms des boutiques dans l’ordre de priorité, séparés par des virgules.\n"
             "Ex : Gafsa, Sousse, Soukra.",
        config_parameter="quelyos_ecom_dynamic_picking.shop_order_names"
    )
