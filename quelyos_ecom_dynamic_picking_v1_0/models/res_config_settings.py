# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    quelyos_dynamic_strategy = fields.Selection([
        ('custom', 'Critères personnalisés'),
        ('disabled', 'Désactivé')
    ], string="Stratégie appliquée", default='custom')

    quelyos_dynamic_stock_basis = fields.Selection([
        ('free', 'Quantité libre'),
        ('onhand', 'Physique (On-Hand)'),
        ('forecast', 'Prévisionnel')
    ], string="Type de stock", default='free')

    quelyos_dynamic_only_website = fields.Boolean(
        string="Appliquer uniquement aux commandes eCommerce",
        default=False
    )

    quelyos_dynamic_central_location_id = fields.Many2one(
        'stock.location', string="Emplacement central"
    )

    # Many2many pour les boutiques (géré via CSV en ir.config_parameter)
    quelyos_dynamic_shop_ids = fields.Many2many(
        'stock.location', string="Boutiques à considérer"
    )

    quelyos_dynamic_strict_order_enabled = fields.Boolean(
        string="Activer l'ordre strict des boutiques"
    )

    quelyos_dynamic_shop_order_names = fields.Char(
        string="Ordre des boutiques"
    )

    # ====== Chargement ======
    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        ICP = self.env['ir.config_parameter'].sudo()
    
        # Fallback pour qu'aucune ancienne valeur invalide ne casse le formulaire
        val = ICP.get_param('quelyos_dynamic_strategy', 'custom')
        if val not in ('custom', 'disabled'):
            val = 'custom'
    
        res.update(
            quelyos_dynamic_strategy=val,
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


    # ====== Sauvegarde ======
    def set_values(self):
        super().set_values()
        ICP = self.env['ir.config_parameter'].sudo()

        ICP.set_param('quelyos_dynamic_strategy', self.quelyos_dynamic_strategy or 'custom')
        ICP.set_param('quelyos_dynamic_stock_basis', self.quelyos_dynamic_stock_basis or 'free')
        ICP.set_param('quelyos_dynamic_only_website', 'True' if self.quelyos_dynamic_only_website else 'False')
        ICP.set_param('quelyos_dynamic_central_location_id', self.quelyos_dynamic_central_location_id.id or 0)
        ICP.set_param('quelyos_dynamic_shop_ids', ','.join(map(str, self.quelyos_dynamic_shop_ids.ids)))
        ICP.set_param('quelyos_dynamic_strict_order_enabled', 'True' if self.quelyos_dynamic_strict_order_enabled else 'False')
        ICP.set_param('quelyos_dynamic_shop_order_names', self.quelyos_dynamic_shop_order_names or '')
