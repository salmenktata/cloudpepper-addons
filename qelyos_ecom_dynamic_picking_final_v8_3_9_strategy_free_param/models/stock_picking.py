# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = "stock.picking"

    qelyos_log = fields.Text(string="Qelyos Dual Log (local)")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if self.env["ir.config_parameter"].sudo().get_param("qelyos_ecom_dynamic_picking.dual_log"):
            for rec in records:
                rec._qelyos_dual_log("create", extra={
                    "origin": rec.origin, "picking_type": rec.picking_type_id.display_name,
                })
        return records

    def action_assign(self):
        res = super().action_assign()
        if self.env["ir.config_parameter"].sudo().get_param("qelyos_ecom_dynamic_picking.dual_log"):
            for rec in self:
                rec._qelyos_dual_log("assign", extra={"reserved": rec.reserved_move_line_ids and True or False})
        return res

    def button_validate(self):
        # Strict order enforcement
        if self.env["ir.config_parameter"].sudo().get_param("qelyos_ecom_dynamic_picking.strict_order"):
            for picking in self:
                picking._qelyos_check_strict_order_before_validate()
        res = super().button_validate()
        if self.env["ir.config_parameter"].sudo().get_param("qelyos_ecom_dynamic_picking.dual_log"):
            for rec in self:
                rec._qelyos_dual_log("validate", extra={"state": rec.state})
        return res

    # --- Helpers ---
    def _qelyos_dual_log(self, event, extra=None):
        """Very light-weight second log: append to qelyos_log field and post a message."""
        msg = "[QELYOS][%s] %s" % (event.upper(), extra or {})
        for rec in self:
            rec.qelyos_log = (rec.qelyos_log or "") + (("\n" if rec.qelyos_log else "") + msg)
            rec.message_post(body=msg)

    def _qelyos_check_strict_order_before_validate(self):
        """Prevent validating this picking if there are other related pickings with lower sequence (type) not done."""
        self.ensure_one()
        if not self.group_id and not self.origin:
            return
        domain = [
            ("id", "!=", self.id),
            ("state", "not in", ("done", "cancel")),
        ]
        # Group has priority if exists, else use origin text
        if self.group_id:
            domain += [("group_id", "=", self.group_id.id)]
        else:
            domain += [("origin", "=", self.origin)]
        # lower sequence means should be done first
        if self.picking_type_id and self.picking_type_id.sequence:
            domain += [("picking_type_id.sequence", "<", self.picking_type_id.sequence)]
        blockers = self.search(domain, limit=1)
        if blockers:
            raise UserError(_("Ordre strict: vous devez d'abord terminer '%s' (type: %s).")
                            % (blockers.display_name, blockers.picking_type_id.display_name))

    # Dynamic source locations (OUT) limited to allowed list when configured
    @api.onchange("location_id", "picking_type_id")
    def _onchange_qelyos_dynamic_source_restrict(self):
        params = self.env["ir.config_parameter"].sudo()
        only_web = params.get_param("qelyos_ecom_dynamic_picking.only_website")
        allowed = self.env["ir.config_parameter"].sudo().get_param("qelyos_ecom_dynamic_picking.allowed_src_ids")
        if allowed:
            try:
                allowed_ids = [int(x) for x in allowed.split(",") if x]
            except Exception:
                allowed_ids = []
        else:
            allowed_ids = []

        if allowed_ids:
            return {"domain": {"location_id": [("id", "in", allowed_ids)]}}
        return {}

class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_confirm(self):
        # Optionally restrict to website orders only
        only_web = self.env["ir.config_parameter"].sudo().get_param("qelyos_ecom_dynamic_picking.only_website")
        res = super()._action_confirm()
        if only_web and not any(self.mapped("website_id")):
            return res
        # Nothing else mandatory here; dynamic selection of source is left to user via allowed domain.
        return res