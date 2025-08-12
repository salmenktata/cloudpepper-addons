# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class StockPicking(models.Model):
    _inherit = "stock.picking"

    quelyos_log = fields.Text(string=_("Quelyos Dual Log (local)"))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if self.env["ir.config_parameter"].sudo().get_param("quelyos_ecom_dynamic_picking.dual_log"):
            for rec in records:
                rec._quelyos_dual_log("create", extra={
                    "origin": rec.origin, "picking_type": rec.picking_type_id.display_name,
                })
        return records

    def write(self, vals):
        # Add server-side validation for source location
        if 'location_id' in vals:
            allowed_ids_str = self.env["ir.config_parameter"].sudo().get_param("quelyos_ecom_dynamic_picking.allowed_src_ids") or ""
            allowed_ids = [int(x) for x in allowed_ids_str.split(",") if x]
            if allowed_ids and vals.get('location_id') and vals['location_id'] not in allowed_ids:
                raise ValidationError(_("L'emplacement source sélectionné n'est pas autorisé."))
        return super(StockPicking, self).write(vals)

    def action_assign(self):
        res = super().action_assign()
        if self.env["ir.config_parameter"].sudo().get_param("quelyos_ecom_dynamic_picking.dual_log"):
            for rec in self:
                rec._quelyos_dual_log("assign", extra={"reserved": bool(rec.reserved_move_line_ids)})
        return res

    def button_validate(self):
        if self.env["ir.config_parameter"].sudo().get_param("quelyos_ecom_dynamic_picking.strict_order"):
            for picking in self:
                picking._quelyos_check_strict_order_before_validate()
        res = super().button_validate()
        if self.env["ir.config_parameter"].sudo().get_param("quelyos_ecom_dynamic_picking.dual_log"):
            for rec in self:
                rec._quelyos_dual_log("validate", extra={"state": rec.state})
        return res

    def _quelyos_dual_log(self, event, extra=None):
        """ Log an event and post a message on the picking. """
        msg = "[QUELYOS][%s] %s" % (event.upper(), extra or {})
        for rec in self:
            rec.quelyos_log = (rec.quelyos_log or "") + (("\n" if rec.quelyos_log else "") + msg)
            rec.message_post(body=msg)

    def _quelyos_check_strict_order_before_validate(self):
        """
        Checks if other related pickings in the same group or with the same origin
        need to be validated first, based on picking type sequence.
        """
        self.ensure_one()
        if not self.group_id and not self.origin:
            return
        domain = [("id", "!=", self.id), ("state", "not in", ("done", "cancel"))]
        if self.group_id:
            domain += [("group_id", "=", self.group_id.id)]
        else:
            domain += [("origin", "=", self.origin)]
        if self.picking_type_id and self.picking_type_id.sequence:
            domain += [("picking_type_id.sequence", "<", self.picking_type_id.sequence)]
        blockers = self.search(domain, limit=1)
        if blockers:
            raise UserError(_("Ordre strict: vous devez d'abord terminer '%s' (type: %s).")
                            % (blockers.display_name, blockers.picking_type_id.display_name))

    @api.onchange("location_id", "picking_type_id")
    def _onchange_quelyos_dynamic_source_restrict(self):
        allowed = self.env["ir.config_parameter"].sudo().get_param("quelyos_ecom_dynamic_picking.allowed_src_ids")
        allowed_ids = []
        if allowed:
            try:
                allowed_ids = [int(x) for x in allowed.split(",") if x]
            except Exception:
                allowed_ids = []
        if allowed_ids:
            return {"domain": {"location_id": [("id", "in", allowed_ids)]}}
        return {}

class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_confirm(self):
        only_web = self.env["ir.config_parameter"].sudo().get_param("quelyos_ecom_dynamic_picking.only_website")
        res = super()._action_confirm()
        if only_web and not any(self.mapped("website_id")):
            return res
        return res
