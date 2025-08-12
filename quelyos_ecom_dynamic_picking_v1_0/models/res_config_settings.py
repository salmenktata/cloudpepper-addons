# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    quelyos_dynamic_only_website = fields.Boolean(
        string="Activer uniquement pour eCommerce",
        config_parameter="quelyos_ecom_dynamic_picking.only_website",
        help="Si activé, n'applique les règles dynamiques que pour les commandes Website."
    )

    quelyos_dynamic_source_location_ids = fields.Many2many(
        "stock.location",
        "quelyos_ecom_src_loc_rel",
        "config_id",
        "location_id",
        string="Emplacements source autorisés",
        help="Emplacements source qui peuvent être assignés dynamiquement aux mouvements sortants."
    )

    quelyos_in_steps = fields.Selection([
        ("1", "IN en 1 étape (Réception)"),
        ("2", "IN en 2 étapes (Entrée → Stock)"),
        ("3", "IN en 3 étapes (Entrée → Contrôle → Stock)"),
    ], string="Flux IN (réceptions)", default="1")

    quelyos_out_steps = fields.Selection([
        ("1", "OUT en 1 étape (Livrer)"),
        ("2", "OUT en 2 étapes (Préparer → Livrer)"),
        ("3", "OUT en 3 étapes (Préparer → Emballer → Livrer)"),
    ], string="Flux OUT (livraisons)", default="1")

    quelyos_strict_order = fields.Boolean(
        string="Ordre strict des opérations (par groupe)",
        config_parameter="quelyos_ecom_dynamic_picking.strict_order",
    )

    quelyos_dual_log = fields.Boolean(
        string="Journalisation Dual-Log",
        config_parameter="quelyos_ecom_dynamic_picking.dual_log",
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

    @api.model
    def get_values(self):
        res = super().get_values()
        params = self.env["ir.config_parameter"].sudo()
        ids_str = params.get_param("quelyos_ecom_dynamic_picking.allowed_src_ids") or ""
        ids = [int(x) for x in ids_str.split(",") if x]
        res.update({
            "quelyos_dynamic_source_location_ids": [(6, 0, ids)]
        })
        return res
