# -*- coding: utf-8 -*-
{
    'name': "Quelyos - Données de configuration",
    'version': '1.0',
    'summary': "Crée les données de configuration par défaut pour le module de picking dynamique.",
    'description': """
Ce module installe la configuration initiale requise par le module 'Quelyos - Dynamic Picking',
incluant les emplacements de stock et les types d'opérations.
    """,
    'author': "Quelyos",
    'website': "https://quelyos.com",
    'category': 'Inventory/Inventory',
    'depends': ['quelyos_ecom_dynamic_picking'],
    'data': [
        'data/quelyos_config_data.xml',
    ],
    'installable': True,
    'auto_install': False, # Cela permet d'installer ce module manuellement
    'license': 'LGPL-3',
}
