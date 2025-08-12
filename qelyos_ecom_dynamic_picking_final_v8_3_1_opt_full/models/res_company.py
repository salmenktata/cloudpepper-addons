# -*- coding: utf-8 -*-
from odoo import fields, models

class ResCompany(models.Model):
    _inherit = "res.company"

    ecom_dynamic_enabled = fields.Boolean(
        string="Enable Dynamic Picking (Qelyos)",
        help="Activate dynamic 1/2/3-step picking for PICK and OUT, plus strict order enforcement and dual log."
    )
    ecom_dynamic_pick_steps = fields.Selection(
        [("one", "1 step"), ("two", "2 steps"), ("three", "3 steps")],
        string="PICK Steps",
        default="one",
        help="Target step configuration for picking operations (warehouse internal pickings)."
    )
    ecom_dynamic_out_steps = fields.Selection(
        [("one", "1 step"), ("two", "2 steps"), ("three", "3 steps")],
        string="OUT Steps",
        default="one",
        help="Target step configuration for outgoing deliveries."
    )
    ecom_dynamic_strict_order = fields.Boolean(
        string="Strict Move Order",
        help="Moves in a picking must be processed in sequence order."
    )
    ecom_dynamic_dual_log = fields.Boolean(
        string="Dual Log (Detailed)",
        help="Post detailed chatter logs on reservation/validation and on sequence enforcement."
    )
    ecom_dynamic_only_website = fields.Boolean(
        string="Website Orders Only",
        help="Apply rules only to pickings originating from website orders."
    )
    ecom_dynamic_strategy = fields.Selection(
        [("balanced", "Balanced (default)"), ("speed", "Favor Speed"), ("accuracy", "Favor Accuracy")],
        string="Dynamic Strategy",
        default="balanced",
        help="High-level hint for dynamic behavior. Independent from routes."
    )
    ecom_dynamic_source_location_ids = fields.Many2many(
        "stock.location",
        "qelyos_company_source_loc_rel",
        "company_id",
        "location_id",
        string="Preferred Source Locations",
        help="Optional: guide source locations for internal transfers/pickings."
    )
