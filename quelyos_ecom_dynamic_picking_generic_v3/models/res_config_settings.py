# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    quelyos_dynamic_strategy = fields.Selection([
        ('custom', 'Stratégie basée sur les règles ci-dessous'),
        ('disabled', 'Désactivé')
    ], string="Stratégie appliquée", default='custom', config_parameter='quelyos_dynamic_strategy', readonly=False)

    quelyos_dynamic_only_website = fields.Boolean(
        string="N’appliquer que sur les commandes eCommerce",
        default=False, config_parameter='quelyos_dynamic_only_website', readonly=False
    )
    
    # Bouton pour accéder à la gestion des règles
    def action_open_dynamic_picking_rules(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Règles de Picking Dynamique'),
            'res_model': 'quelyos.dynamic.picking.rule',
            'view_mode': 'tree,form',
            'target': 'current',
        }
