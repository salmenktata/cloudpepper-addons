# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # --- Stratégie & base de stock (persistés automatiquement) ---
    quelyos_strategy = fields.Selection(
        [("disabled", "Disabled"), ("custom", "Custom Criteria")],
        string="Applied Strategy",
        default="custom",
        config_parameter="quelyos_ecom_dynamic_picking.strategy",
        help="Disabled: no auto selection. Custom: choose source location based on stock & rules.",
    )

    quelyos_stock_basis = fields.Selection(
        [("free", "Free Quantity"), ("onhand", "On-Hand"), ("forecast", "Forecast")],
        string="Stock Basis",
        default="free",
        config_parameter="quelyos_ecom_dynamic_picking.stock_basis",
        help="How availability is computed per location.",
    )

    quelyos_strict_shop_order_enabled = fields.Boolean(
        string="Ordre strict des boutiques (priorité)",
        config_parameter="quelyos_ecom_dynamic_picking.strict_shop_order_enabled",
        help="Si activé, on teste les boutiques selon l'ordre défini et on choisit la première qui couvre tout.",
    )

    quelyos_shop_order_names = fields.Char(
        string="Ordre des boutiques (noms séparés par , ou >)",
        default="Gafsa,Sousse,Soukra",
        config_parameter="quelyos_ecom_dynamic_picking.shop_order_names",
        help="Ex: 'Gafsa,Sousse,Soukra'",
    )

    # --- Portée & options (persistés automatiquement) ---
    quelyos_dynamic_only_website = fields.Boolean(
        string="Activer uniquement pour eCommerce",
        config_parameter="quelyos_ecom_dynamic_picking.only_website",
    )
    quelyos_strict_order = fields.Boolean(
        string="Ordre strict des opérations (par groupe)",
        config_parameter="quelyos_ecom_dynamic_picking.strict_order",
    )
    quelyos_dual_log = fields.Boolean(
        string="Journalisation Dual-Log",
        config_parameter="quelyos_ecom_dynamic_picking.dual_log",
    )

    # --- Emplacements (M2O auto, M2M manuel) ---
    quelyos_central_location_id = fields.Many2one(
        "stock.location",
        string="Emplacement Central (CENT/Stock)",
        domain=[("usage", "=", "internal")],
        config_parameter="quelyos_ecom_dynamic_picking.central_location_id",
    )

    # Boutiques prises en compte par la stratégie (M2M => via set/get)
    quelyos_shop_location_ids = fields.Many2many(
        "stock.location",
        "quelyos_ecom_shop_loc_rel",
        "config_id",
        "location_id",
        string="Boutiques à considérer",
        domain=[("usage", "=", "internal")],
    )

    # Restriction UI des emplacements source (M2M => via set/get)
    quelyos_dynamic_source_location_ids = fields.Many2many(
        "stock.location",
        "quelyos_ecom_src_loc_rel",
        "config_id",
        "location_id",
        string="Emplacements source autorisés (restriction UI)",
        domain=[("usage", "=", "internal")],
    )

    # --- Étapes IN/OUT (pas besoin de config_parameter : bouton applique directement sur warehouses) ---
    quelyos_in_steps = fields.Selection(
        [("1", "IN en 1 étape (Réception)"),
         ("2", "IN en 2 étapes (Entrée → Stock)"),
         ("3", "IN en 3 étapes (Entrée → Contrôle → Stock)")],
        string="Flux IN (réceptions)", default="1"
    )
    quelyos_out_steps = fields.Selection(
        [("1", "OUT en 1 étape (Livrer)"),
         ("2", "OUT en 2 étapes (Préparer → Livrer)"),
         ("3", "OUT en 3 étapes (Préparer → Emballer → Livrer)")],
        string="Flux OUT (livraisons)", default="1"
    )

    def action_quelyos_apply_steps_to_all_warehouses(self):
        self.ensure_one()
        in_map = {"1": "one_step", "2": "two_steps", "3": "three_steps"}
        out_map = {"1": "ship_only", "2": "pick_ship", "3": "pick_pack_ship"}
        warehouses = self.env["stock.warehouse"].search([])
        for wh in warehouses:
            wh._quelyos_set_in_steps(in_map[self.quelyos_in_steps])
            wh._quelyos_set_out_steps(out_map[self.quelyos_out_steps])
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Flux appliqués"),
                       "message": _("Réglages IN/OUT appliqués à tous les entrepôts."),
                       "sticky": False},
        }

    # --------- Persistance manuelle pour les M2M uniquement ---------
    def set_values(self):
        res = super().set_values()
        params = self.env["ir.config_parameter"].sudo()

        shop_ids = ",".join(str(x) for x in self.quelyos_shop_location_ids.ids) if self.quelyos_shop_location_ids else ""
        params.set_param("quelyos_ecom_dynamic_picking.shop_ids", shop_ids)

        src_ids = ",".join(str(x) for x in self.quelyos_dynamic_source_location_ids.ids) if self.quelyos_dynamic_source_location_ids else ""
        params.set_param("quelyos_ecom_dynamic_picking.allowed_src_ids", src_ids)
        return res

    @api.model
    def get_values(self):
        res = super().get_values()
        P = self.env["ir.config_parameter"].sudo()

        shop_ids = [int(x) for x in (P.get_param("quelyos_ecom_dynamic_picking.shop_ids") or "").split(",") if x]
        src_ids = [int(x) for x in (P.get_param("quelyos_ecom_dynamic_picking.allowed_src_ids") or "").split(",") if x]

        res.update({
            "quelyos_shop_location_ids": [(6, 0, shop_ids)],
            "quelyos_dynamic_source_location_ids": [(6, 0, src_ids)],
        })
        return res
