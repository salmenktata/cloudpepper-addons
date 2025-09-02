# -*- coding: utf-8 -*-
import logging
from odoo import models

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    def _get_domain_locations(self):
        """
        Odoo réserve classiquement dans child_of(location_id).
        Quand le contexte 'quelyos_force_exact_location' est présent,
        on resserre le domaine pour NE prendre que l'emplacement exact.
        (Version avec logs de debug.)
        """
        res = super()._get_domain_locations()

        if not self.env.context.get("quelyos_force_exact_location"):
            return res

        # ---- DEBUG: tracer côté logs + chatter du picking si possible
        try:
            # log serveur
            _logger.info(
                "Quelyos EXACT: _get_domain_locations for move %s (src=%s)",
                self.display_name,
                self.location_id.display_name,
            )
            # log chatter (si on a un picking_id)
            for p in self.mapped("picking_id"):
                try:
                    p.message_post(
                        body="⚡ DEBUG Quelyos: réservation EXACT activée "
                             f"(move={self.display_name}, src={self.location_id.display_name})"
                    )
                except Exception:
                    pass
        except Exception:
            pass
        # ---- /DEBUG

        def _tighten(domain_list, loc_ids):
            if not isinstance(domain_list, list):
                return domain_list
            for i, term in enumerate(domain_list):
                if (
                    isinstance(term, tuple)
                    and len(term) == 3
                    and term[0] in ("location_id", "location_src_id")
                    and term[1] == "child_of"
                ):
                    domain_list[i] = (term[0], "in", loc_ids)
            return domain_list

        try:
            loc_ids = self.location_id.ids
            if isinstance(res, (list, tuple)) and len(res) >= 2:
                src_domain, dest_domain = res[0], res[1]
                src_domain = _tighten(src_domain, loc_ids)
                return (src_domain, dest_domain)
        except Exception as e:
            _logger.info("Quelyos DP: exact-location tightening failed: %s", e)
        return res
