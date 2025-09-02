# -*- coding: utf-8 -*-
import logging
from odoo import models

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = "stock.move"

    def _get_domain_locations(self):
        res = super()._get_domain_locations()
        if self.env.context.get("quelyos_force_exact_location"):
            self.env["stock.picking"].sudo().message_post(
                body="⚡ DEBUG Quelyos: reservation EXACT activée sur move %s (loc=%s)"
                % (self.display_name, self.location_id.display_name)
            )
            if isinstance(res, (list, tuple)) and len(res) >= 2:
                src_domain, dest_domain = res[0], res[1]
                for i, term in enumerate(src_domain):
                    if (
                        isinstance(term, tuple)
                        and term[0] in ("location_id", "location_src_id")
                        and term[1] == "child_of"
                    ):
                        src_domain[i] = (term[0], "in", self.location_id.ids)
                return (src_domain, dest_domain)
        return res
