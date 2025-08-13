# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class QuelyosDynamicPickingRule(models.Model):
    _name = 'quelyos.dynamic.picking.rule'
    _description = 'Règle de sélection dynamique de l\'emplacement'
    _order = 'sequence, id'

    name = fields.Char(string="Nom de la règle", required=True)
    sequence = fields.Integer(string="Séquence", default=10, help="Définit l'ordre d'évaluation des règles.")
    active = fields.Boolean(string="Active", default=True)
    
    rule_type = fields.Selection([
        ('central', 'Priorité à l\'emplacement central (si stock suffisant)'),
        ('best_coverage', 'Meilleure couverture (calcul de score pondéré)'),
        ('strict_order', 'Ordre strict des boutiques (première qui couvre tout)'),
        ('specific_shop', 'Emplacement(s) spécifique(s)')
    ], string="Type de règle", required=True, default='best_coverage')

    # Critères
    product_category_id = fields.Many2one('product.category', string="Pour la catégorie de produits")
    
    # Paramètres de la règle
    central_location_id = fields.Many2one(
        'stock.location', string="Emplacement central (CENT/Stock)",
        help="Emplacement à considérer pour la règle 'Priorité au central'."
    )
    
    shop_ids = fields.Many2many(
        'stock.location', string="Boutiques à considérer",
        help="Liste des boutiques à évaluer pour les règles."
    )
    
    shop_order_names = fields.Char(
        string="Ordre strict (ex: Gafsa>Sousse)",
        help="Séparez par '>' (ex: Gafsa>Sousse>Soukra). Utilisé par la règle 'Ordre strict'."
    )
    
    # Paramètres de pondération (pour la règle 'Meilleure couverture')
    weighted_score_enabled = fields.Boolean(string="Activer le score pondéré", default=True)
    stock_coverage_weight = fields.Float(string="Poids de la couverture de stock", default=1.0)
    stock_availability_weight = fields.Float(string="Poids de la disponibilité du stock", default=1.0)
    
    stock_basis = fields.Selection([
        ('free', 'Quantité libre'),
        ('onhand', 'Physique (On-Hand)'),
        ('forecast', 'Prévisionnel')
    ], string="Type de stock", default='free')

