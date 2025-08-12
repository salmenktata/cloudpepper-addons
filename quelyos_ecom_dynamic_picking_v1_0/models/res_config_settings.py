# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    quelyos_dynamic_strategy = fields.Selection(
        selection=[
            ('one_step', '1 Step'),
            ('two_steps', '2 Steps'),
            ('three_steps', '3 Steps')
        ],
        string="Dynamic Picking Strategy",
        default='one_step'
    )

    quelyos_dynamic_source_location_ids = fields.Many2many(
        'stock.location',
        string="Source Locations"
    )

    quelyos_dynamic_only_website = fields.Boolean(
        string="Apply Only to Website Orders",
        default=False
    )

    # Chargement des valeurs
    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        ICP = self.env['ir.config_parameter'].sudo()

        res.update(
            quelyos_dynamic_strategy=ICP.get_param('quelyos_dynamic_strategy', default='one_step'),
            quelyos_dynamic_only_website=ICP.get_param('quelyos_dynamic_only_website', default='False') == 'True'
        )

        location_ids = ICP.get_param('quelyos_dynamic_source_location_ids')
        if location_ids:
            res.update(
                quelyos_dynamic_source_location_ids=[(6, 0, list(map(int, location_ids.split(','))))]
            )
        else:
            res.update(quelyos_dynamic_source_location_ids=False)

        return res

    # Sauvegarde des valeurs
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        ICP = self.env['ir.config_parameter'].sudo()

        ICP.set_param('quelyos_dynamic_strategy', self.quelyos_dynamic_strategy or 'one_step')
        ICP.set_param('quelyos_dynamic_only_website', 'True' if self.quelyos_dynamic_only_website else 'False')

        if self.quelyos_dynamic_source_location_ids:
            ICP.set_param(
                'quelyos_dynamic_source_location_ids',
                ','.join(map(str, self.quelyos_dynamic_source_location_ids.ids))
            )
        else:
            ICP.set_param('quelyos_dynamic_source_location_ids', '')
