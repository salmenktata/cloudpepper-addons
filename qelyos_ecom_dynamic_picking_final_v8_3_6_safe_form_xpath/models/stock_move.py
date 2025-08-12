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
            move_stats = {}
            for m in moves:
                done_qty = sum(m.move_line_ids.mapped("qty_done"))
                remaining = max(m.product_uom_qty - done_qty, 0.0)
                move_stats[m.id] = {"remaining": remaining, "done_any": done_qty > 0.0, "seq": m.sequence, "state": m.state}
            first_unfinished = next((m for m in moves if move_stats[m.id]["remaining"] > 0 and move_stats[m.id]["state"] not in ("done","cancel")), None)
            if not first_unfinished:
                continue
            prior_seq = move_stats[first_unfinished.id]["seq"]
            offending = next((m for m in moves if move_stats[m.id]["seq"] > prior_seq and move_stats[m.id]["done_any"]), None)
            if offending:
                raise UserError(_("Strict move order is enabled. Please complete items in sequence before proceeding."))
        return True
