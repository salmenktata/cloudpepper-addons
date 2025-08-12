# -*- coding: utf-8 -*-
from odoo import fields, models

class ResCompany(models.Model):
    _inherit = "res.company"

    ecom_dynamic_enabled = fields.Boolean(string="Enable Dynamic Picking (Qelyos)")
    ecom_dynamic_only_website = fields.Boolean(string="Website Orders Only")
    ecom_dynamic_strict_order = fields.Boolean(string="Strict Move Order")
    ecom_dynamic_dual_log = fields.Boolean(string="Dual Log (Detailed)")
    ecom_dynamic_pick_steps = fields.Selection([("one","1 step"),("two","2 steps"),("three","3 steps")], default="one")
    ecom_dynamic_out_steps = fields.Selection([("one","1 step"),("two","2 steps"),("three","3 steps")], default="one")
    ecom_dynamic_source_location_ids = fields.Many2many(
        "stock.location",
        "qelyos_company_source_loc_rel",
        "company_id",
        "location_id",
        string="Preferred Source Locations")
