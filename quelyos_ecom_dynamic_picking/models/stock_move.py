# -*- coding: utf-8 -*-
import logging
from odoo import models

_logger = logging.getLogger(__name__)

# Log de chargement à l'import (doit apparaître au boot / upgrade)
_logger.warning("QDP: stock_move override LOADED")


class StockMove(models.Model):
    _inherit = "stock.move"

    def _get_domain_locations(self):
        """
        Par défaut, Odoo réserve dans child_of(location_id).
        Avec le contexte 'quelyos_force_exact_location', on resserre pour NE prendre
        que l'emplacement exact (location_id IN [move.location_id]).
        """
        res = super()._get_domain_locations()

        # Si pas de contexte "exact", on garde le comportement standard
        if not self.env.context.get("quelyos_force_exact_location"):
            return res

        # --- DEBUG facultatif : log sur le serveur pour confirmer l'activation
        try:
            _logger.info(
                "QDP EXACT: move=%s, src=%s",
                self.display_name,
                self.location_id.display_name if self.location_id else "N/A",
            )
        except Exception:
            pass

        def tighten(domain_list, loc_ids):
            """Remplace ('location_id','child_of',X) par ('location_id','in',loc_ids)"""
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
                src_domain = tighten(src_domain, loc_ids)
                return (src_domain, dest_domain)
        except Exception as e:
            _logger.info("QDP: exact-location tightening failed: %s", e)

        return res
