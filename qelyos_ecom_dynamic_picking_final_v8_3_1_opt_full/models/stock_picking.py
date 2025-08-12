# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from time import perf_counter

class StockPicking(models.Model):
    _inherit = "stock.picking"

    qelyos_dynamic_pick_mode = fields.Char(
        string="Qelyos Mode",
        compute="_compute_qelyos_dynamic_pick_mode",
        store=True,
        help="Displays the dynamic step mode applied based on company settings (independent of routes)."
    )

    def _is_website_origin(self):
        self.ensure_one()
        sale = self.sale_id
        if not sale:
            return False
        return bool(getattr(sale, "website_id", False))

    def _qelyos_apply_scope(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        if not company.ecom_dynamic_enabled:
            return False
        if company.ecom_dynamic_only_website and not self._is_website_origin():
            return False
        return True

    @api.depends(
        "picking_type_code",
        "company_id.ecom_dynamic_enabled",
        "company_id.ecom_dynamic_only_website",
        "company_id.ecom_dynamic_pick_steps",
        "company_id.ecom_dynamic_out_steps",
        "sale_id.website_id"
    )
    def _compute_qelyos_dynamic_pick_mode(self):
        for picking in self:
            if not picking._qelyos_apply_scope():
                picking.qelyos_dynamic_pick_mode = ""
                continue
            company = picking.company_id or self.env.company
            if picking.picking_type_code == "outgoing":
                picking.qelyos_dynamic_pick_mode = dict(company._fields["ecom_dynamic_out_steps"].selection).get(company.ecom_dynamic_out_steps, "")
            elif picking.picking_type_code == "internal":
                picking.qelyos_dynamic_pick_mode = dict(company._fields["ecom_dynamic_pick_steps"].selection).get(company.ecom_dynamic_pick_steps, "")
            else:
                picking.qelyos_dynamic_pick_mode = ""

    def _qelyos_profile(self, label, t0):
        if self.env.context.get("qelyos_profile"):
            dt = (perf_counter() - t0) * 1000.0
            self.message_post(body=f"[Qelyos Profile] {label}: {dt:.2f} ms")

    def action_assign(self):
        t0 = perf_counter()
        res = super().action_assign()
        for picking in self:
            if not picking._qelyos_apply_scope():
                continue
            company = picking.company_id
            if company.ecom_dynamic_dual_log:
                picking.message_post(body=_("Qelyos Dual Log: Reservation attempted. Mode: %s") % (picking.qelyos_dynamic_pick_mode or "-"))
        self._qelyos_profile("action_assign", t0)
        return res

    def button_validate(self):
        t0 = perf_counter()
        to_check = self.filtered(lambda p: p._qelyos_apply_scope() and p.company_id.ecom_dynamic_strict_order)
        if to_check:
            to_check.mapped("move_ids_without_package")._check_strict_sequence_before_validate()
        res = super().button_validate()
        for picking in self:
            if picking._qelyos_apply_scope() and picking.company_id.ecom_dynamic_dual_log:
                picking.message_post(body=_("Qelyos Dual Log: Picking validated. Mode: %s") % (picking.qelyos_dynamic_pick_mode or "-"))
        self._qelyos_profile("button_validate", t0)
        return res
