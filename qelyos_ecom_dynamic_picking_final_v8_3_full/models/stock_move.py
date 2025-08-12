# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class StockMove(models.Model):
    _inherit = "stock.move"

    def _check_strict_sequence_before_validate(self):
        """Enforce strict sequence order within the parent picking if enabled at company level.
        A move with higher sequence cannot be processed while a lower sequence move has qty still to process.
        """
        for move in self:
            picking = move.picking_id
            if not picking or not picking.company_id.ecom_dynamic_enabled or not picking.company_id.ecom_dynamic_strict_order:
                continue
            # Only enforce on pickings we are validating or reserving
            moves = picking.move_ids_without_package.sorted(key=lambda m: (m.sequence, m.id))
            # Find the first move not done (qty still to do)
            def _remaining(m):
                # For simplicity, use quantity_done vs product_uom_qty on move lines
                done = sum(m.move_line_ids.mapped("qty_done"))
                return max(m.product_uom_qty - done, 0.0)
            first_unfinished = None
            for m in moves:
                if _remaining(m) > 0 and m.state not in ("done", "cancel"):
                    first_unfinished = m
                    break
            if not first_unfinished:
                continue
            # If any move with a higher sequence is already partially/fully done, raise
            prior_seq = first_unfinished.sequence
            offending = [m for m in moves if m.sequence > prior_seq and any(ml.qty_done > 0 for ml in m.move_line_ids)]
            if offending:
                raise UserError(_("Strict move order is enabled. Please complete items in sequence before proceeding."))
        return True
