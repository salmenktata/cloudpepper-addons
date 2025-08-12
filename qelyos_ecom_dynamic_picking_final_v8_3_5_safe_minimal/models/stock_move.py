# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.exceptions import UserError
class StockMove(models.Model):
    _inherit = "stock.move"
    def _check_strict_sequence_before_validate(self):
        pickings = self.mapped("picking_id")
        for picking in pickings:
            company = picking.company_id
            if not (company.ecom_dynamic_enabled and company.ecom_dynamic_strict_order):
                continue
            moves = picking.move_ids_without_package.sorted(key=lambda m: (m.sequence, m.id))
            if not moves:
                continue
            def remaining(m):
                done = sum(m.move_line_ids.mapped("qty_done"))
                return max(m.product_uom_qty - done, 0.0)
            first_unfinished = next((m for m in moves if remaining(m) > 0 and m.state not in ("done","cancel")), None)
            if not first_unfinished:
                continue
            prior_seq = first_unfinished.sequence
            for m in moves:
                if m.sequence > prior_seq and any(ml.qty_done > 0 for ml in m.move_line_ids):
                    raise UserError(_("Strict move order is enabled. Please complete items in sequence before proceeding."))
        return True
