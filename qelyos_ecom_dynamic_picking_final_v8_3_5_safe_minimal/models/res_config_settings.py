# -*- coding: utf-8 -*-
from odoo import fields, models
class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"
    ecom_dynamic_enabled = fields.Boolean(related="company_id.ecom_dynamic_enabled", readonly=False)
    ecom_dynamic_pick_steps = fields.Selection(related="company_id.ecom_dynamic_pick_steps", readonly=False)
    ecom_dynamic_out_steps = fields.Selection(related="company_id.ecom_dynamic_out_steps", readonly=False)
    ecom_dynamic_strict_order = fields.Boolean(related="company_id.ecom_dynamic_strict_order", readonly=False)
    ecom_dynamic_dual_log = fields.Boolean(related="company_id.ecom_dynamic_dual_log", readonly=False)
    ecom_dynamic_only_website = fields.Boolean(related="company_id.ecom_dynamic_only_website", readonly=False)
    ecom_dynamic_strategy = fields.Selection(related="company_id.ecom_dynamic_strategy", readonly=False)
    ecom_dynamic_source_location_ids = fields.Many2many(related="company_id.ecom_dynamic_source_location_ids", readonly=False)
