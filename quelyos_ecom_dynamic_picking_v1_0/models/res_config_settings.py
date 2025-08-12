# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    quelyos_dynamic_strategy = fields.Selection([
        ('disabled', 'Disabled'),
        ('custom', 'Custom Criteria')
    ], string="Applied Strategy", default='custom')

    quelyos_stock_basis = fields.Selection([
        ('free', 'Free Quantity'),
        ('onhand', 'On-Hand'),
        ('forecast', 'Forecast')
    ], string="Stock Basis", default='free')

    quelyos_order_strict = fields.Boolean(string="Strict Order (Gafsa → Sousse → Soukra)", default=False)

    quelyos_dynamic_source_location_ids = fields.Many2many(
        'stock.location',
        string="Boutiques à considérer"
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        ICP = self.env['ir.config_parameter'].sudo()
        res.update(
            quelyos_dynamic_strategy=ICP.get_param('quelyos_dynamic_strategy', 'custom'),
            quelyos_stock_basis=ICP.get_param('quelyos_stock_basis', 'free'),
            quelyos_order_strict=ICP.get_param('quelyos_order_strict') == 'True',
            quelyos_dynamic_source_location_ids=[(6, 0, list(map(int, ICP.get_param('quelyos_dynamic_source_location_ids', '').split(','))))] if ICP.get_param('quelyos_dynamic_source_location_ids') else False
        )
        return res

    def set_values(self):
        super().set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('quelyos_dynamic_strategy', self.quelyos_dynamic_strategy)
        ICP.set_param('quelyos_stock_basis', self.quelyos_stock_basis)
        ICP.set_param('quelyos_order_strict', 'True' if self.quelyos_order_strict else 'False')
        ICP.set_param('quelyos_dynamic_source_location_ids', ','.join(map(str, self.quelyos_dynamic_source_location_ids.ids)) if self.quelyos_dynamic_source_location_ids else '')
