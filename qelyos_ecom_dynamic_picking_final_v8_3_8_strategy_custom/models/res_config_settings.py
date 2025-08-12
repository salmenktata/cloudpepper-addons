from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ecom_dynamic_enabled = fields.Boolean("Enable Dynamic Picking Strategy")
    ecom_dynamic_strategy = fields.Selection([
        ('qelyos_custom', 'Qelyos Custom Strategy'),
        ('standard', 'Odoo Standard'),
    ], string="Dynamic Picking Strategy", default='qelyos_custom')
    ecom_dynamic_free_stock_only = fields.Boolean("Use only free stock (exclude reserved)", default=True)

    def set_values(self):
        res = super().set_values()
        self.env['ir.config_parameter'].sudo().set_param('ecom_dynamic_enabled', self.ecom_dynamic_enabled)
        self.env['ir.config_parameter'].sudo().set_param('ecom_dynamic_strategy', self.ecom_dynamic_strategy)
        self.env['ir.config_parameter'].sudo().set_param('ecom_dynamic_free_stock_only', self.ecom_dynamic_free_stock_only)
        return res

    def get_values(self):
        res = super().get_values()
        res.update(
            ecom_dynamic_enabled=self.env['ir.config_parameter'].sudo().get_param('ecom_dynamic_enabled', 'False') == 'True',
            ecom_dynamic_strategy=self.env['ir.config_parameter'].sudo().get_param('ecom_dynamic_strategy', 'qelyos_custom'),
            ecom_dynamic_free_stock_only=self.env['ir.config_parameter'].sudo().get_param('ecom_dynamic_free_stock_only', 'True') == 'True'
        )
        return res
