# -*- coding: utf-8 -*-
from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Activation & portée
    quelyos_dynamic_enabled = fields.Boolean(
        string="Activer Quelyos – Dynamic Picking",
        default=False,
    )
    quelyos_dynamic_ecom_only = fields.Boolean(
        string="Limiter aux commandes eCommerce",
        help="N'applique la stratégie qu'aux livraisons issues de commandes web.",
        default=False,
    )

    # Base de stock
    quelyos_dynamic_stock_basis = fields.Selection(
        selection=[("free", "Quantité libre"), ("onhand", "Physique (On-Hand)"), ("forecast", "Prévisionnel")],
        string="Base de stock utilisée",
        default="free",
    )

    # Centre + boutiques
    quelyos_dynamic_central_location_id = fields.Many2one(
        'stock.location',
        string="Emplacement central"
    )
    quelyos_dynamic_locations = fields.Many2many(
        'stock.location',
        string="Boutiques considérées"
    )

    # Ordre strict
    quelyos_dynamic_strict_order_enabled = fields.Boolean(
        string="Activer l'ordre strict des boutiques",
        default=False,
        help="Si coché, l'évaluation suit l'ordre textuel défini ci-dessous."
    )
    quelyos_dynamic_strict_shop_order = fields.Char(
        string="Ordre strict (ex: Gafsa>Sousse>Soukra)",
        help="Séparez par '>' pour imposer un ordre de priorité des boutiques."
    )

    # Réassort auto
    quelyos_dynamic_auto_confirm_replenishment = fields.Boolean(
        string="Auto-confirmer et réserver le réassort",
        default=True
    )
    quelyos_dynamic_auto_validate_replenishment = fields.Boolean(
        string="Auto-valider le réassort s'il est 100% réservé",
        default=True
    )

    # Logs
    quelyos_dynamic_log_success = fields.Boolean(
        string="Afficher un log de succès dans le chatter",
        default=False
    )

    # (NOUVEAU) Couverture partielle
    quelyos_dynamic_partial_enabled = fields.Boolean(
        string="Activer la couverture partielle (Priorité 4)",
        default=True,
        help="Si aucun emplacement ne couvre 100%, choisir l'emplacement offrant la meilleure couverture et, si possible, réassortir le manque depuis le central."
    )
