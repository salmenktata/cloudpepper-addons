# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

# We add the new field to the stock.location model here to avoid a circular import.
class StockLocation(models.Model):
    _inherit = "stock.location"

    quelyos_is_shop = fields.Boolean(
        string=_("Is a Quelyos Shop"),
        help=_("If checked, this location is considered a shop for Quelyos picking strategies.")
    )

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    quelyos_dynamic_only_website = fields.Boolean(
        string=_("Activer uniquement pour eCommerce"),
        config_parameter="quelyos_ecom_dynamic_picking.only_website",
        help=_("Si activé, n'applique les règles dynamiques que pour les commandes Website.")
    )

    quelyos_dynamic_source_location_ids = fields.Many2many(
        "stock.location",
        "quelyos_ecom_src_loc_rel",
        "config_id",
        "location_id",
        string=_("Emplacements source autorisés"),
        help=_("Emplacements source qui peuvent être assignés dynamiquement aux mouvements sortants.")
    )

    quelyos_in_steps = fields.Selection([
        ("1", _("IN en 1 étape (Réception)")),
        ("2", _("IN en 2 étapes (Entrée → Stock)")),
        ("3", _("IN en 3 étapes (Entrée → Contrôle → Stock)")),
    ], string=_("Flux IN (réceptions)"), default="1")

    quelyos_out_steps = fields.Selection([
        ("1", _("OUT en 1 étape (Livrer)")),
        ("2", _("OUT en 2 étapes (Préparer → Livrer)")),
        ("3", _("OUT en 3 étapes (Préparer → Emballer → Livrer)")),
    ], string=_("Flux OUT (livraisons)"), default="1")

    quelyos_strict_order = fields.Boolean(
        string=_("Ordre strict des opérations (par groupe)"),
        config_parameter="quelyos_ecom_dynamic_picking.strict_order",
    )

    quelyos_dual_log = fields.Boolean(
        string=_("Journalisation Dual-Log"),
        config_parameter="quelyos_ecom_dynamic_picking.dual_log",
    )

    # Nouveaux champs pour la stratégie
    quelyos_strategy = fields.Selection([
        ("custom_criteria", _("Critères personnalisés (Custom Criteria)")),
        ("disabled", _("Désactivé")),
    ], string=_("Stratégie de sélection de l'emplacement"), default="custom_criteria")

    quelyos_stock_basis = fields.Selection([
        ("free_quantity", _("Quantité libre (Free Quantity)")),
        ("on_hand", _("Quantité en stock (On-Hand)")),
        ("forecast", _("Stock prévisionnel (Forecast)")),
    ], string=_("Base de calcul des disponibilités"), default="free_quantity")

    quelyos_shop_locations = fields.Many2many(
        "stock.location",
        "quelyos_shop_loc_rel",
        "config_id",
        "shop_location_id",
        string=_("Boutiques à considérer"),
        help=_("Liste des emplacements des boutiques pour le calcul du stock."),
        domain="[('quelyos_is_shop', '=', True)]" # Added domain to filter by shops
    )

    def action_quelyos_apply_steps_to_all_warehouses(self):
        self.ensure_one()
        in_map = {"1": "one_step", "2": "two_steps", "3": "three_steps"}
        out_map = {"1": "ship_only", "2": "pick_ship", "3": "pick_pack_ship"}
        warehouses = self.env["stock.warehouse"].search([])
        for wh in warehouses:
            wh._quelyos_set_in_steps(in_map[self.quelyos_in_steps])
            wh._quelyos_set_out_steps(out_map[self.quelyos_out_steps])
        return { "type": "ir.actions.client", "tag": "display_notification",
                 "params": {"title": _("Flux appliqués"),
                            "message": _("Les réglages IN/OUT ont été appliqués à tous les entrepôts."),
                            "sticky": False} }

    def set_values(self):
        super().set_values()
        params = self.env["ir.config_parameter"].sudo()
        ids_str = ",".join(str(x) for x in self.quelyos_dynamic_source_location_ids.ids) if self.quelyos_dynamic_source_location_ids else ""
        params.set_param("quelyos_ecom_dynamic_picking.allowed_src_ids", ids_str)
        # Enregistrement des nouveaux paramètres
        params.set_param("quelyos_ecom_dynamic_picking.strategy", self.quelyos_strategy)
        params.set_param("quelyos_ecom_dynamic_picking.stock_basis", self.quelyos_stock_basis)
        shop_ids_str = ",".join(str(x) for x in self.quelyos_shop_locations.ids) if self.quelyos_shop_locations else ""
        params.set_param("quelyos_ecom_dynamic_picking.shop_locations", shop_ids_str)

    @api.model
    def get_values(self):
        res = super().get_values()
        params = self.env["ir.config_parameter"].sudo()
        ids_str = params.get_param("quelyos_ecom_dynamic_picking.allowed_src_ids") or ""
        ids = [int(x) for x in ids_str.split(",") if x]

        shop_ids_str = params.get_param("quelyos_ecom_dynamic_picking.shop_locations") or ""
        shop_ids = [int(x) for x in shop_ids_str.split(",") if x]

        res.update({
            "quelyos_dynamic_source_location_ids": [(6, 0, ids)],
            "quelyos_strategy": params.get_param("quelyos_ecom_dynamic_picking.strategy", default="custom_criteria"),
            "quelyos_stock_basis": params.get_param("quelyos_ecom_dynamic_picking.stock_basis", default="free_quantity"),
            "quelyos_shop_locations": [(6, 0, shop_ids)],
        })
        return res
