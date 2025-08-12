# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Website scope
    ecom_dynamic_only_website = fields.Boolean(
        string="Activer uniquement pour eCommerce",
        config_parameter="qelyos_ecom_dynamic_picking.only_website",
        help="Si activé, n'applique les règles dynamiques que pour les commandes Website."
    )

    # Source locations usable for dynamic picking (M2M was missing earlier -> now defined)
    ecom_dynamic_source_location_ids = fields.Many2many(
        "stock.location",
        "qelyos_ecom_src_loc_rel",
        "config_id",
        "location_id",
        string="Emplacements source autorisés",
        help="Emplacements source qui peuvent être assignés dynamiquement aux mouvements sortants."
    )

    # Strategy-free global choices for steps (apply to all warehouses unless overridden)
    ecom_in_steps = fields.Selection([
        ("1", "IN en 1 étape (Réception)"),
        ("2", "IN en 2 étapes (Entrée → Stock)"),
        ("3", "IN en 3 étapes (Entrée → Contrôle → Stock)"),
    ], string="Flux IN (réceptions)", default="1",
       help="Nombre d'étapes pour les réceptions. Application globale si vous cliquez sur 'Appliquer maintenant'.")

    ecom_out_steps = fields.Selection([
        ("1", "OUT en 1 étape (Livrer)"),
        ("2", "OUT en 2 étapes (Préparer → Livrer)"),
        ("3", "OUT en 3 étapes (Préparer → Emballer → Livrer)"),
    ], string="Flux OUT (livraisons)", default="1",
       help="Nombre d'étapes pour les livraisons. Application globale si vous cliquez sur 'Appliquer maintenant'.")

    # Strict order
    ecom_strict_order = fields.Boolean(
        string="Ordre strict des opérations (par groupe)",
        config_parameter="qelyos_ecom_dynamic_picking.strict_order",
        help="Empêche la validation d'un picking si un autre picking lié (même origine/groupe) avec une séquence plus basse n'est pas terminé."
    )

    # Dual log
    ecom_dual_log = fields.Boolean(
        string="Journalisation Dual-Log",
        config_parameter="qelyos_ecom_dynamic_picking.dual_log",
        help="Active une double journalisation simple des évènements clés (création/assignation/validation)."
    )

    # Apply button helpers (no config_parameter to avoid surprise updates)
    def action_apply_steps_to_all_warehouses(self):
        """Apply the chosen IN/OUT steps to all warehouses without touching routes definitions."""
        self.ensure_one()
        in_map = {"1": "one_step", "2": "two_steps", "3": "three_steps"}
        out_map = {"1": "ship_only", "2": "pick_ship", "3": "pick_pack_ship"}
        warehouses = self.env["stock.warehouse"].search([])
        for wh in warehouses:
            # IN
            wh._qelyos_set_in_steps(in_map[self.ecom_in_steps])
            # OUT
            wh._qelyos_set_out_steps(out_map[self.ecom_out_steps])
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Flux appliqués"),
                       "message": _("Les réglages IN/OUT ont été appliqués à tous les entrepôts."),
                       "sticky": False},
        }