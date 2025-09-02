# -*- coding: utf-8 -*-
{
    'name': 'Quelyos – Dynamic Picking (TEST)',
    'version': '2.3.4',
    'summary': "Sélection automatique de l'emplacement source pour les commandes eCommerce",
    'description': """
Ce module permet d'appliquer une stratégie dynamique pour déterminer automatiquement 
l'emplacement source des livraisons selon des critères configurables :
- Priorité au stock central si possible
- Sinon meilleure boutique (stock libre max)
- Réassort automatique si besoin
    """,
    'author': "Quelyos",
    'website': "https://quelyos.com",
    'category': 'Inventory/Inventory',
    'depends': ['sale', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
