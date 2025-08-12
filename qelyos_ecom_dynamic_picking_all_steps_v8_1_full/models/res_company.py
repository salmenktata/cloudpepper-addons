
# -*- coding: utf-8 -*-
from odoo import models, fields

class ResCompany(models.Model):
    _inherit = "res.company"

    ecom_dynamic_source_location_ids = fields.Many2many(
        "stock.location", "res_company_ecom_loc_rel", "company_id", "location_id",
        string="Emplacements sources possibles",
        help="Inclure CENTRAL/Stock et les boutiques (ex: CENT/Stock/Boutique Sousse). Emplacements de type 'Interne' uniquement."
    )

    ecom_dynamic_strategy = fields.Selection(
        [
            ("central_then_max_all_then_order", "CENTRAL > Max dispo (toutes boutiques) > Ordre strict"),
            ("first_available", "Premier emplacement couvrant"),
            ("most_available", "Emplacement avec plus de dispo"),
            ("default_only", "Toujours dépôt par défaut"),
        ],
        default="central_then_max_all_then_order",
        string="Stratégie de sélection",
        help="Règle appliquée aux commandes eCommerce lors de la création des pickings."
    )

    ecom_dynamic_website_id = fields.Many2one(
        "website", string="Limiter à un site web",
        help="Si renseigné, la logique ne s'applique qu'à ce site web (eCommerce)."
    )
