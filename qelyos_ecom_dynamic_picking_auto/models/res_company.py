# -*- coding: utf-8 -*-
from odoo import models, fields

class ResCompany(models.Model):
    _inherit = "res.company"

    ecom_dynamic_source_location_ids = fields.Many2many(
        "stock.location",
        "res_company_ecom_loc_rel",
        "company_id",
        "location_id",
        string="Emplacements sources possibles",
        help="Liste des emplacements (ex: Boutique X/Stock) que la stratégie peut sélectionner comme source d'expédition."
    )

    ecom_dynamic_strategy = fields.Selection(
        selection=[
            ("first_available", "Premier emplacement avec stock"),
            ("default_only", "Toujours dépôt par défaut"),
        ],
        string="Stratégie de sélection",
        default="first_available",
        help="Règle de sélection de l'emplacement source lors de la création du picking eCommerce."
    )

    ecom_dynamic_website_id = fields.Many2one(
        "website",
        string="Limiter à un site web",
        help="Si renseigné, la stratégie ne s'applique qu'à ce site web."
    )
