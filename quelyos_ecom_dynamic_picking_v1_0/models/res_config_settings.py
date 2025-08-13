# -*- coding: utf-8 -*-
from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Activer/désactiver la logique (si besoin d’un ON/OFF global)
    quelyos_dynamic_enabled = fields.Boolean(
        string="Activer le picking dynamique",
        default=True,
        help="Si décoché, aucun choix automatique de l’emplacement source ne sera appliqué."
    )

    # Base de calcul utilisée pour évaluer les stocks
    quelyos_dynamic_stock_basis = fields.Selection([
        ('free', 'Quantité libre'),
        ('onhand', 'Physique (On-Hand)'),
        ('forecast', 'Prévisionnel'),
    ], string="Type de stock (base de calcul)",
       default='free',
       help="exp : « Quantité libre » = physique − réservé ; « Prévisionnel » inclut les mouvements confirmés à venir.")

    # Limiter l’application aux commandes eCommerce
    quelyos_dynamic_only_website = fields.Boolean(
        string="Appliquer uniquement aux commandes eCommerce",
        default=False,
        help="exp : si coché, la stratégie ne s’applique qu’aux commandes passées via le site web."
    )

    # Emplacement central (critère 1)
    quelyos_dynamic_central_location_id = fields.Many2one(
        'stock.location',
        string="Emplacement central (CENT/Stock)",
        help="exp : emplacement prioritaire si son stock couvre toute la commande."
    )

    # Boutiques à considérer (critère 2 puis 3) — l’ordre d’ajout est utilisé pour le critère 3
    quelyos_dynamic_shop_ids = fields.Many2many(
        'stock.location',
        'res_company_quelyos_dynamic_shop_rel',
        'company_id', 'location_id',
        string="Boutiques à considérer (ordre d’ajout)",
        help="exp : sélectionnez les boutiques. L’ordre d’ajout détermine la priorité pour le critère 3."
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Champs liés à la société (modifiables depuis la vue de paramètres)
    quelyos_dynamic_enabled = fields.Boolean(
        related='company_id.quelyos_dynamic_enabled',
        readonly=False,
        string="Activer le picking dynamique",
        help="Si décoché, aucun choix automatique de l’emplacement source ne sera appliqué."
    )

    quelyos_dynamic_stock_basis = fields.Selection(
        related='company_id.quelyos_dynamic_stock_basis',
        readonly=False,
        selection=[
            ('free', 'Quantité libre'),
            ('onhand', 'Physique (On-Hand)'),
            ('forecast', 'Prévisionnel'),
        ],
        string="Type de stock (base de calcul)",
        help="exp : « Quantité libre » = physique − réservé ; « Prévisionnel » inclut les mouvements confirmés à venir."
    )

    quelyos_dynamic_only_website = fields.Boolean(
        related='company_id.quelyos_dynamic_only_website',
        readonly=False,
        string="Appliquer uniquement aux commandes eCommerce",
        help="exp : si coché, la stratégie ne s’applique qu’aux commandes passées via le site web."
    )

    quelyos_dynamic_central_location_id = fields.Many2one(
        related='company_id.quelyos_dynamic_central_location_id',
        readonly=False,
        comodel_name='stock.location',
        string="Emplacement central (CENT/Stock)",
        help="exp : emplacement prioritaire si son stock couvre toute la commande."
    )

    quelyos_dynamic_shop_ids = fields.Many2many(
        related='company_id.quelyos_dynamic_shop_ids',
        readonly=False,
        comodel_name='stock.location',
        string="Boutiques à considérer (ordre d’ajout)",
        help="exp : l’ordre choisi ici sera utilisé pour le critère 3."
    )
