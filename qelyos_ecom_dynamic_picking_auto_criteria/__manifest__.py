# -*- coding: utf-8 -*-
{
    "name": "eCommerce – Sélection dynamique (CENTRAL > Max stock > Ordre fixe) + réassort",
    "summary": "Priorité CENTRAL si possible, sinon magasin avec plus de stock (Gafsa/Sousse/Tunis), sinon ordre Gafsa>Sousse>Tunis. Réassort auto si besoin.",
    "version": "18.0.3.0.0",
    "author": "Qelyos",
    "website": "https://qelyos.com",
    "depends": ["sale", "stock", "website_sale"],
    "data": [
        "views/res_config_settings_views.xml"
    ],
    "application": False,
    "license": "LGPL-3"
}
