# -*- coding: utf-8 -*-
{
    "name": "Qelyos eCommerce Dynamic Picking (v8.3.1 Optimized)",
    "summary": "Dynamic 1/2/3-step picking for PICK/OUT, strict order, dual log — optimized & profiled",
    "version": "18.0.8.3.1",
    "author": "Qelyos",
    "license": "LGPL-3",
    "website": "https://qelyos.com",
    "category": "Inventory/Customization",
    "depends": ["stock", "sale_management", "website_sale", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/stock_picking_views.xml"
    ],
    "assets": {},
    "installable": True,
    "application": False,
    "auto_install": False,
    "post_init_hook": "post_init_hook"
}
