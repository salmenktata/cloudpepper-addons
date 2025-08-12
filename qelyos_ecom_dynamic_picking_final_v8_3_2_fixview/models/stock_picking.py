from odoo import api,fields,models,_
from time import perf_counter
class StockPicking(models.Model):
    _inherit='stock.picking'
    qelyos_dynamic_pick_mode = fields.Char(compute='_compute_qelyos_dynamic_pick_mode', store=True)
    def _is_website_origin(self):
        self.ensure_one(); s=self.sale_id; return bool(getattr(s,'website_id',False)) if s else False
    def _qelyos_apply_scope(self):
        self.ensure_one(); c=self.company_id or self.env.company
        if not c.ecom_dynamic_enabled: return False
        if c.ecom_dynamic_only_website and not self._is_website_origin(): return False
        return True
    @api.depends('picking_type_code','company_id.ecom_dynamic_enabled','company_id.ecom_dynamic_only_website','company_id.ecom_dynamic_pick_steps','company_id.ecom_dynamic_out_steps','sale_id.website_id')
    def _compute_qelyos_dynamic_pick_mode(self):
        for p in self:
            if not p._qelyos_apply_scope(): p.qelyos_dynamic_pick_mode=''; continue
            c=p.company_id or self.env.company
            p.qelyos_dynamic_pick_mode = (dict(c._fields['ecom_dynamic_out_steps'].selection).get(c.ecom_dynamic_out_steps,'') if p.picking_type_code=='outgoing' else (dict(c._fields['ecom_dynamic_pick_steps'].selection).get(c.ecom_dynamic_pick_steps,'') if p.picking_type_code=='internal' else ''))
    def _qelyos_profile(self,label,t0):
        if self.env.context.get('qelyos_profile'):
            dt=(perf_counter()-t0)*1000.0; self.message_post(body=f'[Qelyos Profile] {label}: {dt:.2f} ms')
    def action_assign(self):
        t0=perf_counter(); res=super().action_assign()
        for p in self:
            if not p._qelyos_apply_scope(): continue
            if p.company_id.ecom_dynamic_dual_log:
                p.message_post(body=_('Qelyos Dual Log: Reservation attempted. Mode: %s') % (p.qelyos_dynamic_pick_mode or '-'))
        self._qelyos_profile('action_assign',t0); return res
    def button_validate(self):
        t0=perf_counter(); to_check=self.filtered(lambda p:p._qelyos_apply_scope() and p.company_id.ecom_dynamic_strict_order)
        if to_check:
            to_check.mapped('move_ids_without_package')._check_strict_sequence_before_validate()
        res=super().button_validate()
        for p in self:
            if p._qelyos_apply_scope() and p.company_id.ecom_dynamic_dual_log:
                p.message_post(body=_('Qelyos Dual Log: Picking validated. Mode: %s') % (p.qelyos_dynamic_pick_mode or '-'))
        self._qelyos_profile('button_validate',t0); return res
