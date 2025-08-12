from odoo import models,_
from odoo.exceptions import UserError
class StockMove(models.Model):
    _inherit='stock.move'
    def _check_strict_sequence_before_validate(self):
        pickings = self.mapped('picking_id')
        for picking in pickings:
            c = picking.company_id
            if not (c.ecom_dynamic_enabled and c.ecom_dynamic_strict_order):
                continue
            moves = picking.move_ids_without_package.sorted(key=lambda m:(m.sequence,m.id))
            if not moves:
                continue
            stats={}
            for m in moves:
                dq=sum(m.move_line_ids.mapped('qty_done'))
                stats[m.id]={'rem': max(m.product_uom_qty-dq,0.0), 'done_any': dq>0.0, 'seq': m.sequence}
            fu=None
            for m in moves:
                if stats[m.id]['rem']>0 and m.state not in ('done','cancel'):
                    fu=m; break
            if not fu:
                continue
            prior=stats[fu.id]['seq']
            for m in moves:
                if stats[m.id]['seq']>prior and stats[m.id]['done_any']:
                    raise UserError(_('Strict move order is enabled. Please complete items in sequence before proceeding.'))
        return True
