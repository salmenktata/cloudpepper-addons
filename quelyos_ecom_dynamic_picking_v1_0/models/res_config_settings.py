# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    quelyos_dynamic_strategy = fields.Selection([
        ('custom', 'Critères personnalisés'),
        ('disabled', 'Désactivé')
    ], string="Stratégie appliquée", default='custom',
       help="Exp : 'Critères personnalisés' applique l'algorithme intelligent, "
            "'Désactivé' désactive la sélection automatique.")

    quelyos_dynamic_stock_basis = fields.Selection([
        ('free', 'Quantité libre'),
        ('onhand', 'Physique (On-Hand)'),
        ('forecast', 'Prévisionnel')
    ], string="Type de stock", default='free',
       help="Exp : Choisit la base de calcul des stocks. "
            "Quantité libre = Physique - Réservations, "
            "Physique = quantité réelle, "
            "Prévisionnel = prend en compte les entrées à venir.")

    quelyos_dynamic_only_website = fields.Boolean(
        string="Appliquer uniquement aux commandes eCommerce",
        default=False,
        help="Exp : Si coché, la stratégie ne s'appliquera que pour les commandes issues du site eCommerce."
    )

    quelyos_dynamic_central_location_id = fields.Many2one(
        'stock.location', string="Emplacement central",
        help="Exp : L'entrepôt central utilisé en priorité (ex : CENT/Stock)."
    )

    quelyos_dynamic_shop_ids = fields.Many2many(
        'stock.location', string="Boutiques à considérer",
        help="Exp : Boutiques physiques prises en compte dans le calcul automatique."
    )

    quelyos_dynamic_shop_order_names = fields.Char(
        string="Ordre des boutiques (Critère 3)",
        default="Gafsa,Sousse,Soukra",
        help="Exp : Ordre fixe utilisé à l'étape 3 si aucune source unique ne couvre toute la commande."
    )

    # ====== Chargement ======
    @api.model
    def get_values(self):
        res = super().get_values()
        ICP = self.env['ir.config_parameter'].sudo()

        # Fallback stratégie
        val = ICP.get_param('quelyos_dynamic_strategy', 'custom')
        if val not in ('custom', 'disabled'):
            val = 'custom'

        res.update(
            quelyos_dynamic_strategy=val,
            quelyos_dynamic_stock_basis=ICP.get_param('quelyos_dynamic_stock_basis', 'free'),
            quelyos_dynamic_only_website=ICP.get_param('quelyos_dynamic_only_website', 'False') == 'True',
            quelyos_dynamic_central_location_id=int(ICP.get_param('quelyos_dynamic_central_location_id', 0)) or False,
            quelyos_dynamic_shop_order_names=ICP.get_param('quelyos_dynamic_shop_order_names', 'Gafsa,Sousse,Soukra')
        )

        shop_ids = ICP.get_param('quelyos_dynamic_shop_ids')
        if shop_ids:
            res.update(quelyos_dynamic_shop_ids=[(6, 0, list(map(int, shop_ids.split(','))))])
        else:
            res.update(quelyos_dynamic_shop_ids=False)

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
        ICP.set_param('quelyos_dynamic_shop_order_names', self.quelyos_dynamic_shop_order_names or 'Gafsa,Sousse,Soukra')
