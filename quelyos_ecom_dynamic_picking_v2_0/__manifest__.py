# -*- coding: utf-8 -*-
{
    'name': "Quelyos - Dynamic Picking",
    'version': '2.0',
    'summary': "Sélection automatique de l'emplacement source pour les commandes eCommerce basée sur des règles dynamiques.",
    'description': """
Ce module permet d'appliquer une stratégie dynamique et personnalisable pour déterminer automatiquement 
l'emplacement source des livraisons selon un ensemble de règles définies par l'utilisateur.

Fonctionnalités :
- Stratégie de sélection basée sur des règles ordonnées et configurables.
- Possibilité de définir des règles spécifiques par catégorie de produit.
- Réassort automatique en cas de besoin.
- Gestion intuitive des règles via une interface dédiée.
- Calcul de score pondéré pour une sélection encore plus fine.
    """,
    'author': "Quelyos",
    'website': "https://quelyos.com",
    'category': 'Inventory/Inventory',
    'depends': ['sale', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/quelyos_dynamic_picking_rule_views.xml',
        'views/res_config_settings_views.xml',
        'data/quelyos_config_data.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
