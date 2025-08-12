# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class StockPicking(models.Model):
    _inherit = "stock.picking"

    # non-stored to avoid heavy recompute at install
    qelyos_dynamic_pick_mode = fields.Char(
        string="Qelyos Mode",
        compute="_compute_qelyos_dynamic_pick_mode",
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
