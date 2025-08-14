# -*- coding: utf-8 -*-
from odoo import api, fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Activation + portée
    quelyos_dynamic_enabled = fields.Boolean(
        string="Activer Quelyos – Dynamic Picking",
        config_parameter="quelyos_dynamic_enabled",
        help="Active la stratégie de sélection dynamique d'emplacement source pour les livraisons sortantes."
    )
    quelyos_dynamic_ecom_only = fields.Boolean(
        string="Limiter aux commandes eCommerce",
        config_parameter="quelyos_dynamic_ecom_only",
        help="N'applique la stratégie qu'aux livraisons issues de commandes web (Sale Order avec website)."
    )

    # Base de stock
    quelyos_dynamic_stock_basis = fields.Selection(
        selection=[("free", "Quantité libre"), ("onhand", "Physique (On-Hand)"), ("forecast", "Prévisionnel")],
        default="free",
        config_parameter="quelyos_dynamic_stock_basis",
        string="Base de stock utilisée"
    )

    # Centre + boutiques
    quelyos_dynamic_central_location_id = fields.Many2one(
        "stock.location",
        string="Emplacement central",
        help="Emplacement 'central' prioritaire si capable de couvrir toute la commande."
    )
    quelyos_dynamic_shop_ids = fields.Many2many(
        "stock.location",
        string="Boutiques considérées",
        help="Liste des emplacements (boutiques) à considérer par la stratégie."
    )

    # Ordre strict
    quelyos_dynamic_strict_order_enabled = fields.Boolean(
        string="Activer l'ordre strict des boutiques",
        config_parameter="quelyos_dynamic_strict_order_enabled",
        help="Si activé : la première boutique de la liste d'ordre strict capable de couvrir toute la commande est choisie."
    )
    quelyos_dynamic_strict_shop_order = fields.Char(
        string="Ordre strict (ex: Gafsa>Sousse>Soukra)",
        config_parameter="quelyos_dynamic_strict_shop_order",
        help="Saisir les noms (ou parties de noms) des boutiques séparés par '>' dans l'ordre de priorité."
    )

    # Réassort interne : confirmation/réservation automatique
    quelyos_dynamic_auto_confirm_replenishment = fields.Boolean(
        string="Auto-confirmer et réserver le réassort",
        default=True,
        config_parameter="quelyos_dynamic_auto_confirm_replenishment",
        help="Après création du réassort interne, le module le confirme et tente la réservation automatique."
    )

    # ✅ NOUVEAU : Auto-validation du réassort si 100% réservé
    quelyos_dynamic_auto_validate_replenishment = fields.Boolean(
        string="Auto-valider le réassort s'il est 100% réservé",
        default=True,
        config_parameter="quelyos_dynamic_auto_validate_replenishment",
        help="Si toutes les lignes du réassort sont entièrement réservées, valide automatiquement le picking interne."
    )

    # Persistance Many2one/Many2many via ICP
    @api.model
    def get_values(self):
        res = super().get_values()
        ICP = self.env["ir.config_parameter"].sudo()
        central_id = int(ICP.get_param("quelyos_dynamic_central_location_id", default="0") or 0)
        shops = (ICP.get_param("quelyos_dynamic_shop_ids", default="") or "").strip()
        shop_ids = []
        if shops:
            try:
                shop_ids = [int(x) for x in shops.split(",") if x.strip().isdigit()]
            except Exception:
                shop_ids = []
        res.update(
            quelyos_dynamic_central_location_id=central_id or False,
            quelyos_dynamic_shop_ids=[(6, 0, shop_ids)] if shop_ids else False,
        )
        return res

    def set_values(self):
        super().set_values()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param(
            "quelyos_dynamic_central_location_id",
            str(self.quelyos_dynamic_central_location_id.id or "")
        )
        ICP.set_param(
            "quelyos_dynamic_shop_ids",
            ",".join(map(str, self.quelyos_dynamic_shop_ids.ids)) if self.quelyos_dynamic_shop_ids else ""
        )
