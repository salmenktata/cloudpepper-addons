# -*- coding: utf-8 -*-
from odoo import models, fields

class ResCompany(models.Model):
    _inherit = "res.company"

    ecom_dynamic_source_location_ids = fields.Many2many(
        "stock.location", "res_company_ecom_loc_rel", "company_id", "location_id",
        string="Emplacements sources possibles",
        help="Inclure CENTRAL/Stock et les boutiques (Gafsa/Sousse/Tunis...)."
    )

    ecom_dynamic_strategy = fields.Selection(
        [
            ("first_available", "Premier emplacement avec stock"),
            ("most_available", "Emplacement avec plus de stock (disponible)"),
            ("central_then_maxstock_then_order", "CENTRAL > Max stock (Gafsa/Sousse/Tunis) > Ordre fixe (Gafsa>Sousse>Tunis)"),
            ("default_only", "Toujours dépôt par défaut"),
        ],
        default="central_then_maxstock_then_order",
        string="Stratégie de sélection",
    )

    ecom_dynamic_website_id = fields.Many2one(
        "website", string="Limiter à un site web",
        help="Si renseigné, la logique ne s'applique qu'à ce site web (eCommerce)."
    )
