# -*- coding: utf-8 -*-
from odoo import fields, models

class ResCompany(models.Model):
    _inherit = "res.company"

    quelyos_dynamic_enabled = fields.Boolean(
        string="Activer Picking Dynamique Qelyos",
        default=False,
        help="Si coché, active la logique de picking dynamique pour cette société."
    )

    quelyos_dynamic_shop_ids = fields.Many2many(
        'stock.location',
        'res_company_quelyos_dynamic_shop_rel',
        'company_id', 'location_id',
        string="Boutiques à considérer",
        help="Liste des boutiques à considérer pour le picking dynamique, l'ordre défini ici sera utilisé pour le critère 3."
    )
