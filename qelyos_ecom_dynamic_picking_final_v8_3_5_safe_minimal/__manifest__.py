# -*- coding: utf-8 -*-
{
    "name": "Qelyos eCommerce Dynamic Picking (v8.3.5 SAFE minimal)",
    "summary": "Dynamic 1/2/3-step display, strict order check (SAFE: no post_init, non-stored compute, guarded logs)",
    "version": "18.0.8.3.5",
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
