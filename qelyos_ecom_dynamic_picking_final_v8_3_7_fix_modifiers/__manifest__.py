# -*- coding: utf-8 -*-
{
    "name": "Qelyos eCommerce Dynamic Picking (v8.3.7 Modifiers Fix)",
    "summary": "Dynamic 1/2/3-step picking, strict order, dual log — safe install + OWL modifiers",
    "version": "18.0.8.3.7",
    "author": "Qelyos",
    "license": "LGPL-3",
    "website": "https://qelyos.com",
    "category": "Inventory/Customization",
    "depends": ["base", "stock", "sale_management", "website_sale", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/stock_picking_views.xml"
    ],
    "assets": {},
    "installable": True,
    "application": False,
    "auto_install": False
}
