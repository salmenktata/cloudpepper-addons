# -*- coding: utf-8 -*-
from odoo import fields, models

class ResCompany(models.Model):
    _inherit = "res.company"

    # Active/désactive globalement la logique de picking dynamique pour la société
    quelyos_dynamic_enabled = fields.Boolean(
        string="Activer le picking dynamique Quelyos",
        default=False,
        help="Lorsque activé, la sélection automatique de l'emplacement source "
             "et le réassort interne sont appliqués sur les livraisons sortantes."
    )
