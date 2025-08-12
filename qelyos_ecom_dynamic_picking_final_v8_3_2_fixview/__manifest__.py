# -*- coding: utf-8 -*-
{
    "name": "Qelyos eCommerce Dynamic Picking (v8.3.2 View Fix)",
    "version": "18.0.8.3.2",
    "summary": "Fix settings view inheritance for Odoo 17/18 + previous optimizations",
    "author": "Qelyos",
    "license": "LGPL-3",
    "website": "https://qelyos.com",
    "category": "Inventory/Customization",
    "depends": ["stock", "sale_management", "website_sale", "mail", "base"],
    "data": [
        "views/res_config_settings_views.xml",
        "views/stock_picking_views.xml",
        "security/ir.model.access.csv"
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
