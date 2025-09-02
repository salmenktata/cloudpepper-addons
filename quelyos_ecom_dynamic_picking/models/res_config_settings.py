# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Tous les champs sont related à res.company (source de vérité)
    quelyos_dynamic_enabled = fields.Boolean(
        string="Activer Quelyos – Dynamic Picking",
        related="company_id.quelyos_dynamic_enabled",
        readonly=False
    )
    quelyos_dynamic_ecom_only = fields.Boolean(
        string="Limiter aux commandes eCommerce",
        related="company_id.quelyos_dynamic_ecom_only",
        readonly=False
    )

    quelyos_dynamic_stock_basis = fields.Selection(
        selection=[("free", "Quantité libre"), ("onhand", "Physique (On-Hand)"), ("forecast", "Prévisionnel")],
        string="Base de stock utilisée",
        related="company_id.quelyos_dynamic_stock_basis",
        readonly=False
    )

    quelyos_dynamic_central_location_id = fields.Many2one(
        "stock.location",
        string="Emplacement central",
        related="company_id.quelyos_dynamic_central_location_id",
        readonly=False
    )
    quelyos_dynamic_shop_ids = fields.Many2many(
        "stock.location",
        string="Boutiques considérées",
        related="company_id.quelyos_dynamic_locations",
        readonly=False
    )

    quelyos_dynamic_strict_order_enabled = fields.Boolean(
        string="Activer l'ordre strict des boutiques",
        related="company_id.quelyos_dynamic_strict_order_enabled",
        readonly=False
    )
    quelyos_dynamic_strict_shop_order = fields.Char(
        string="Ordre strict (ex: Gafsa>Sousse>Soukra)",
        related="company_id.quelyos_dynamic_strict_shop_order",
        readonly=False
    )

    quelyos_dynamic_auto_confirm_replenishment = fields.Boolean(
        string="Auto-confirmer et réserver le réassort",
        related="company_id.quelyos_dynamic_auto_confirm_replenishment",
        readonly=False
    )
    quelyos_dynamic_auto_validate_replenishment = fields.Boolean(
        string="Auto-valider le réassort s'il est 100% réservé",
        related="company_id.quelyos_dynamic_auto_validate_replenishment",
        readonly=False
    )

    quelyos_dynamic_log_success = fields.Boolean(
        string="Afficher un log de succès dans le chatter",
        related="company_id.quelyos_dynamic_log_success",
        readonly=False
    )

    # (NOUVEAU) Couverture partielle
    quelyos_dynamic_partial_enabled = fields.Boolean(
        string="Activer la couverture partielle (Priorité 4)",
        related="company_id.quelyos_dynamic_partial_enabled",
        readonly=False
    )
