# -*- coding: utf-8 -*-
{
    'name': "Quelyos - Données de configuration",
    'version': '1.0',
    'summary': "Crée les données de configuration par défaut pour le module de picking dynamique.",
    'description': """
Ce module installe la configuration initiale requise par le module 'Quelyos - Dynamic Picking',
incluant les emplacements de stock, les types d'opérations et les paramètres par défaut du module Ventes.
    """,
    'author': "Quelyos",
    'website': "https://quelyos.com",
    'category': 'Inventory/Inventory',
    'depends': ['quelyos_ecom_dynamic_picking', 'sale_management', 'point_of_sale', 'account'],
    'data': [
        'data/quelyos_config_data.xml',
        'data/sale_config_data.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
