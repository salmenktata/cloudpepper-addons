# -*- coding: utf-8 -*-
import logging
from odoo import models

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    def _get_domain_locations(self):
        """
        Par défaut, Odoo réserve dans child_of(location_id).
        Si le contexte 'quelyos_force_exact_location' est posé, on resserre le domaine
        pour NE prendre que l’emplacement source EXACT (pas les enfants).
        """
        res = super()._get_domain_locations()

        # Ne resserrer que sur demande explicite
        if not self.env.context.get("quelyos_force_exact_location"):
            return res

        def _tighten(domain_list, loc_ids):
            if not isinstance(domain_list, list):
                return domain_list
            for i, term in enumerate(domain_list):
                if (
                    isinstance(term, tuple)
                    and len(term) == 3
                    and term[0] in ("location_id", "location_id", "location_src_id")
                    and term[1] in ("child_of", "child_of")
                ):
                    left, _, _ = term
                    domain_list[i] = (left, "in", loc_ids)
            return domain_list

        try:
            # Tous les moves ciblés par la stratégie partagent le même location_id
            loc_ids = self.location_id.ids
            if isinstance(res, (list, tuple)) and len(res) >= 2:
                domain_src, domain_dest = res[0], res[1]
                domain_src = _tighten(domain_src, loc_ids)
                return (domain_src, domain_dest)
        except Exception as e:
            _logger.info(
                "Quelyos DP: _get_domain_locations tighten failed (%s). Fallback to parent behavior.", e
            )
        return res
