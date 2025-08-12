# Champs persistés automatiquement
quelyos_strategy = fields.Selection(
    [("disabled", "Disabled"), ("custom", "Custom Criteria")],
    default="custom",
    string="Applied Strategy",
    config_parameter="quelyos_ecom_dynamic_picking.strategy",
)

quelyos_stock_basis = fields.Selection(
    [("free", "Free Quantity"), ("onhand", "On-Hand"), ("forecast", "Forecast")],
    default="free",
    string="Stock Basis",
    config_parameter="quelyos_ecom_dynamic_picking.stock_basis",
)

quelyos_strict_shop_order_enabled = fields.Boolean(
    string="Ordre strict des boutiques (priorité)",
    config_parameter="quelyos_ecom_dynamic_picking.strict_shop_order_enabled",
)

quelyos_shop_order_names = fields.Char(
    string="Ordre des boutiques (noms séparés par , ou >)",
    default="Gafsa,Sousse,Soukra",
    config_parameter="quelyos_ecom_dynamic_picking.shop_order_names",
)

quelyos_dynamic_only_website = fields.Boolean(
    string="Activer uniquement pour eCommerce",
    config_parameter="quelyos_ecom_dynamic_picking.only_website",
)

quelyos_strict_order = fields.Boolean(
    string="Ordre strict des opérations (par groupe)",
    config_parameter="quelyos_ecom_dynamic_picking.strict_order",
)

quelyos_dual_log = fields.Boolean(
    string="Journalisation Dual-Log",
    config_parameter="quelyos_ecom_dynamic_picking.dual_log",
)

quelyos_central_location_id = fields.Many2one(
    "stock.location",
    string="Emplacement Central (CENT/Stock)",
    domain=[("usage", "=", "internal")],
    config_parameter="quelyos_ecom_dynamic_picking.central_location_id",
)

# M2M -> via set_values/get_values
quelyos_shop_location_ids = fields.Many2many(
    "stock.location", "quelyos_ecom_shop_loc_rel", "config_id", "location_id",
    string="Boutiques à considérer", domain=[("usage", "=", "internal")]
)

quelyos_dynamic_source_location_ids = fields.Many2many(
    "stock.location", "quelyos_ecom_src_loc_rel", "config_id", "location_id",
    string="Emplacements source autorisés (restriction UI)", domain=[("usage", "=", "internal")]
)

def set_values(self):
    res = super().set_values()
    P = self.env["ir.config_parameter"].sudo()
    shop_ids = ",".join(str(x) for x in self.quelyos_shop_location_ids.ids) if self.quelyos_shop_location_ids else ""
    P.set_param("quelyos_ecom_dynamic_picking.shop_ids", shop_ids)
    src_ids = ",".join(str(x) for x in self.quelyos_dynamic_source_location_ids.ids) if self.quelyos_dynamic_source_location_ids else ""
    P.set_param("quelyos_ecom_dynamic_picking.allowed_src_ids", src_ids)
    return res

@api.model
def get_values(self):
    res = super().get_values()
    P = self.env["ir.config_parameter"].sudo()
    shop_ids = [int(x) for x in (P.get_param("quelyos_ecom_dynamic_picking.shop_ids") or "").split(",") if x]
    src_ids = [int(x) for x in (P.get_param("quelyos_ecom_dynamic_picking.allowed_src_ids") or "").split(",") if x]
    res.update({
        "quelyos_shop_location_ids": [(6, 0, shop_ids)],
        "quelyos_dynamic_source_location_ids": [(6, 0, src_ids)],
    })
    return res
