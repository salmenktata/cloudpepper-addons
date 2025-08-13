# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    quelyos_dynamic_strategy = fields.Selection([
        ('custom', 'Personnalisée'),
        ('default', 'Par défaut')
    ], string="Stratégie Dynamic Picking", default='custom')

    quelyos_dynamic_stock_basis = fields.Selection([
        ('free', 'Quantité libre'),
        ('onhand', 'Quantité en stock'),
        ('forecast', 'Quantité prévisionnelle')
    ], string="Base de calcul du stock", default='free')

    quelyos_dynamic_only_website = fields.Boolean(
        string="Appliquer uniquement aux commandes Website"
    )

    quelyos_dynamic_central_location_id = fields.Many2one(
        'stock.location', string="Emplacement central"
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        ICP = self.env['ir.config_parameter'].sudo()
        res.update(
            quelyos_dynamic_strategy=ICP.get_param('quelyos_dynamic_strategy', 'custom'),
            quelyos_dynamic_stock_basis=ICP.get_param('quelyos_dynamic_stock_basis', 'free'),
            quelyos_dynamic_only_website=ICP.get_param('quelyos_dynamic_only_website', 'False') == 'True',
            quelyos_dynamic_central_location_id=int(ICP.get_param('quelyos_dynamic_central_location_id', '0')) or False,
        )
        return res

    def set_values(self):
        super().set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('quelyos_dynamic_strategy', self.quelyos_dynamic_strategy)
        ICP.set_param('quelyos_dynamic_stock_basis', self.quelyos_dynamic_stock_basis)
        ICP.set_param('quelyos_dynamic_only_website', self.quelyos_dynamic_only_website)
        ICP.set_param('quelyos_dynamic_central_location_id', self.quelyos_dynamic_central_location_id.id or 0)
