# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    quelyos_dynamic_strategy = fields.Selection([
        ('custom', 'Critères personnalisés (auto-sélection + réassort)'),
        ('disabled', 'Désactivé')
    ], string="Stratégie appliquée", default='custom',
       help="Détermine la logique utilisée pour choisir automatiquement l'emplacement source des livraisons.")

    quelyos_dynamic_stock_basis = fields.Selection([
        ('free', 'Quantité libre (physique - réservé)'),
        ('onhand', 'Physique (On-Hand)'),
        ('forecast', 'Prévisionnel (inclut mouvements confirmés)')
    ], string="Type de stock", default='free',
       help="Base de calcul des disponibilités pour déterminer la source optimale.")

    quelyos_dynamic_only_website = fields.Boolean(
        string="Appliquer uniquement aux commandes eCommerce",
        default=False,
        help="Si activé, la stratégie dynamique ne s'applique qu'aux commandes provenant du site web."
    )

    quelyos_dynamic_central_location_id = fields.Many2one(
        'stock.location',
        string="Emplacement central",
        help="Entrepôt central à utiliser en priorité si le stock est suffisant."
    )

    quelyos_dynamic_shop_ids = fields.Many2many(
        'stock.location',
        string="Boutiques à considérer",
        help="Liste des boutiques à inclure dans la recherche d'un emplacement source alternatif."
    )

    quelyos_dynamic_strict_order_enabled = fields.Boolean(
        string="Activer l'ordre strict des boutiques",
        help="Si activé, les boutiques sont testées dans l'ordre défini ci-dessous."
    )

    quelyos_dynamic_shop_order_names = fields.Char(
        string="Ordre des boutiques",
        help="Ordre des boutiques séparées par des virgules (ex : Gafsa, Sousse, Soukra)."
    )

    # ====== Chargement des paramètres ======
    @api.model
    def get_values(self):
        res = super().get_values()
        ICP = self.env['ir.config_parameter'].sudo()

        # Stratégie
        val_strategy = ICP.get_param('quelyos_dynamic_strategy', 'custom')
        if val_strategy not in ('custom', 'disabled'):
            val_strategy = 'custom'

        res.update(
            quelyos_dynamic_strategy=val_strategy,
            quelyos_dynamic_stock_basis=ICP.get_param('quelyos_dynamic_stock_basis', 'free'),
            quelyos_dynamic_only_website=ICP.get_param('quelyos_dynamic_only_website', 'False') == 'True',
            quelyos_dynamic_central_location_id=self.env['stock.location'].browse(int(ICP.get_param('quelyos_dynamic_central_location_id') or 0)),
            quelyos_dynamic_strict_order_enabled=ICP.get_param('quelyos_dynamic_strict_order_enabled', 'False') == 'True',
            quelyos_dynamic_shop_order_names=ICP.get_param('quelyos_dynamic_shop_order_names', '') or ''
        )

        # Boutiques
        shop_ids = ICP.get_param('quelyos_dynamic_shop_ids')
        if shop_ids:
            res.update(
                quelyos_dynamic_shop_ids=[(6, 0, list(map(int, shop_ids.split(','))))]
            )
        else:
            res.update(quelyos_dynamic_shop_ids=False)

        return res

    # ====== Sauvegarde des paramètres ======
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
