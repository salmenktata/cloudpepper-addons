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
    ], string="Type de stock utilisé", default='free')

    quelyos_dynamic_only_website = fields.Boolean(
        string="N’appliquer que sur les commandes eCommerce",
        default=False
    )

    quelyos_dynamic_central_location_id = fields.Many2one(
        'stock.location', string="Emplacement central (CENT/Stock)",
        help="exp : si l’emplacement central couvre toute la commande, il sera choisi en priorité."
    )

    quelyos_dynamic_shop_ids = fields.Many2many(
        'stock.location', string="Boutiques à considérer",
        help="exp : liste des boutiques à évaluer si le central ne couvre pas tout."
    )

    quelyos_dynamic_strict_order_enabled = fields.Boolean(
        string="Activer l’ordre strict (Gafsa → Sousse → Soukra)",
        help="exp : teste les boutiques dans l’ordre indiqué ci‑dessous et sélectionne la première qui couvre toute la commande."
    )

    quelyos_dynamic_shop_order_names = fields.Char(
        string="Ordre des boutiques (ex: Gafsa>Sousse>Soukra)",
        help="exp : séparez par '>' (ex: Gafsa>Sousse>Soukra)."
    )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        ICP = self.env['ir.config_parameter'].sudo()

        val = ICP.get_param('quelyos_dynamic_strategy', 'custom')
        if val not in ('custom', 'disabled'):
            val = 'custom'

        res.update(
            quelyos_dynamic_strategy=val,
            quelyos_dynamic_stock_basis=ICP.get_param('quelyos_dynamic_stock_basis', 'free'),
            quelyos_dynamic_only_website=ICP.get_param('quelyos_dynamic_only_website', 'False') in ('1', 'True', 'true'),
        )

        central = ICP.get_param('quelyos_dynamic_central_location_id', '0')
        res.update(quelyos_dynamic_central_location_id=int(central) or False)

        shop_ids = ICP.get_param('quelyos_dynamic_shop_ids', '')
        shop_ids_list = [int(x) for x in shop_ids.split(',') if x]
        res.update(quelyos_dynamic_shop_ids=[(6, 0, shop_ids_list)] if shop_ids_list else False)

        res.update(
            quelyos_dynamic_strict_order_enabled=ICP.get_param('quelyos_dynamic_strict_order_enabled', 'False') in ('1', 'True', 'true'),
            quelyos_dynamic_shop_order_names=ICP.get_param('quelyos_dynamic_shop_order_names', '') or '',
        )
        return res

    def set_values(self):
        super().set_values()
        ICP = self.env['ir.config_parameter'].sudo()

        strategy = self.quelyos_dynamic_strategy if self.quelyos_dynamic_strategy in ('custom', 'disabled') else 'custom'
        basis = self.quelyos_dynamic_stock_basis if self.quelyos_dynamic_stock_basis in ('free', 'onhand', 'forecast') else 'free'
        
        ICP.set_param('quelyos_dynamic_strategy', strategy)
        ICP.set_param('quelyos_dynamic_stock_basis', basis)
        ICP.set_param('quelyos_dynamic_only_website', '1' if self.quelyos_dynamic_only_website else '0')
        ICP.set_param('quelyos_dynamic_central_location_id', self.quelyos_dynamic_central_location_id.id or 0)
        ICP.set_param('quelyos_dynamic_shop_ids', ','.join(map(str, self.quelyos_dynamic_shop_ids.ids)) if self.quelyos_dynamic_shop_ids else '')
        ICP.set_param('quelyos_dynamic_strict_order_enabled', '1' if self.quelyos_dynamic_strict_order_enabled else '0')
        ICP.set_param('quelyos_dynamic_shop_order_names', self.quelyos_dynamic_shop_order_names or '')