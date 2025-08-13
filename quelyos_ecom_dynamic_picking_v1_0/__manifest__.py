# -*- coding: utf-8 -*-
{
    "name": "Quelyos - Dynamic Picking (v1.0 - Strategy Free Param)",
    "summary": "Auto-select source for deliveries with smart stock-based strategy + internal replenishment; plus IN/OUT steps, strict order & dual-log.",
    "version": "1.0",
    "author": "Quelyos",
    "website": "https://quelyos.com",
    "license": "LGPL-3",
    "category": "Inventory/Inventory",
    "depends": ["stock", "sale_management", "website_sale"],
    "data": [
        "views/res_config_settings_views.xml",
        "views/stock_views.xml",
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": False,
    "auto_install": False
}
