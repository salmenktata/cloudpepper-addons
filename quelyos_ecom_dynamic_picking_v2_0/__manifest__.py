# -*- coding: utf-8 -*-
manifest = {
    "name": "Quelyos - Dynamic Picking (v1.0)",
    "summary": "Sélection automatique de la source + réassort interne (Quelyos)",
    "version": "1.0",
    "author": "Quelyos",
    "website": "https://quelyos.example",
    "category": "Inventory/Logistics",
    "license": "LGPL-3",
    "depends": [
        "sale",
        "stock"
    ],
    "data": [
        "views/res_config_settings_views.xml"
    ],
    "installable": true,
    "application": false
}