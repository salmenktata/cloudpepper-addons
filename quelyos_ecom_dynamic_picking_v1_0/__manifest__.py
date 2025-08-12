# -*- coding: utf-8 -*-
{
    "name": "Quelyos - Dynamic Picking (v1.0 - Strategy Free Param)",
    "summary": "Dynamic 1/2/3-step IN & OUT, strict order option, dual-log, strategy-free parameters, internal transfers support",
    "version": "1.0",
    "author": "Quelyos",
    "website": "https://quelyos.com",
    "license": "LGPL-3",
    "category": "Inventory/Inventory",
    "depends": ["stock", "sale_management", "website_sale"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/stock_views.xml",
        "views/menu.xml"
    ],
    "installable": True,
    "application": False,
    "auto_install": False
}
