from odoo import fields, models

class ResCompany(models.Model):
    _inherit='res.company'
    ecom_dynamic_enabled = fields.Boolean()
    ecom_dynamic_pick_steps = fields.Selection([('one','1 step'),('two','2 steps'),('three','3 steps')], default='one')
    ecom_dynamic_out_steps = fields.Selection([('one','1 step'),('two','2 steps'),('three','3 steps')], default='one')
    ecom_dynamic_strict_order = fields.Boolean()
    ecom_dynamic_dual_log = fields.Boolean()
    ecom_dynamic_only_website = fields.Boolean()
    ecom_dynamic_strategy = fields.Selection([('balanced','Balanced'),('speed','Favor Speed'),('accuracy','Favor Accuracy')], default='balanced')
    ecom_dynamic_source_location_ids = fields.Many2many('stock.location', 'qelyos_company_source_loc_rel', 'company_id', 'location_id')
