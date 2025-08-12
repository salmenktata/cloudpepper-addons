# -*- coding: utf-8 -*-
{
    "name": "Qelyos - Dynamic Picking (Final v8.3.9c - Strategy Free Param)",
    "summary": "Dynamic 1/2/3-step IN & OUT, strict order option, dual-log, strategy-free parameters, internal transfers support",
    "version": "18.0.8.3.9.1",
    "author": "Qelyos",
    "website": "https://qelyos.com",
    "license": "LGPL-3",
    "category": "Inventory/Inventory",
    "depends": ["stock", "sale_management", "website_sale"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/qelyos_settings_menu.xml",
        "views/stock_views.xml"
    ],
    "installable": True,
    "application": False,
    "auto_install": False
}
