# -*- coding: utf-8 -*-
from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ecom_dynamic_source_location_ids = fields.Many2many(
        "stock.location", related="company_id.ecom_dynamic_source_location_ids", readonly=False
    )
    ecom_dynamic_strategy = fields.Selection(
        [
            ("central_then_max_then_order_strict", "CENTRAL > Max dispo (boutiques) > Ordre strict (Gafsa>Sousse>Soukra)"),
            ("first_available", "Premier emplacement avec stock"),
            ("most_available", "Emplacement avec plus de stock (disponible)"),
            ("default_only", "Toujours dépôt par défaut"),
        ],
        related="company_id.ecom_dynamic_strategy",
        readonly=False,
    )
    ecom_dynamic_website_id = fields.Many2one(
        "website", related="company_id.ecom_dynamic_website_id", readonly=False
    )
