# qelyos_ecom_dynamic_picking/__manifest__.py
{
    "name": "eCommerce Dynamic Picking (Multi‑Stores)",
    "summary": "Choisit automatiquement le magasin expéditeur optimal pour les commandes web",
    "version": "18.0.1.0",
    "author": "Qelyos",
    "website": "https://qelyos.com",
    "license": "LGPL-3",
    "depends": ["sale_management", "stock", "website_sale"],
    "data": [
        "views/res_config_settings_views.xml",
        "security/ir.model.access.csv"
    ],
    "application": False,
    "installable": True
}