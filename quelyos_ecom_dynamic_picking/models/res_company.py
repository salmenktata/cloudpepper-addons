# -*- coding: utf-8 -*-
from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    quelyos_dynamic_enabled = fields.Boolean("Activer Quelyos – Dynamic Picking")
    quelyos_dynamic_locations = fields.Many2many(
        'stock.location',
        string="Boutiques considérées"
    )
    quelyos_dynamic_central_location_id = fields.Many2one(
        'stock.location',
        string="Emplacement central"
    )
    quelyos_dynamic_auto_replenish = fields.Boolean(
        string="Auto-confirmer et réserver le réassort",
        default=True
    )
