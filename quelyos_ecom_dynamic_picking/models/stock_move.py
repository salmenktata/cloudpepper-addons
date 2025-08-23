# -*- coding: utf-8 -*-
import logging
from odoo import models

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = "stock.move"

    def _get_domain_locations(self):
        """
        Sur Odoo, par défaut la réservation cherche dans `child_of(location_id)`.
        Avec le contexte `quelyos_force_exact_location=True`, on resserre le domaine
        pour ne prendre que l’emplacement source EXACT (pas les enfants).
        """
        res = super()._get_domain_locations()

        if not self.env.context.get("quelyos_force_exact_location"):
            return res

        # Selon versions, res peut être (domain_src, domain_dest) ou une structure équivalente.
        # On cible le domaine "source".
        def _tighten(dom, loc_ids):
            try:
                dom_list = list(dom)
            except Exception:
                return dom
            for i, term in enumerate(dom_list):
                # term est un tuple ('location_id', 'child_of', ids) => on remplace par 'in'
                if isinstance(term, (list, tuple)) and len(term) >= 3:
                    left, op, right = term[0], term[1], term[2]
                    if left in ("location_id", "location_src_id", "location") and op == "child_of":
                        dom_list[i] = (left, "in", loc_ids)
            return dom_list

        try:
            # Quand appelé sur un recordset, tous nos moves d'un picking ont été
            # reciblés vers le même location_id par Quelyos.
            loc_ids = self.location_id.ids
            if isinstance(res, (list, tuple)) and len(res) >= 2:
                domain_src, domain_dest = res[0], res[1]
                domain_src = _tighten(domain_src, loc_ids)
                return (domain_src, domain_dest)
        except Exception as e:
            _logger.info("Quelyos DP: _get_domain_locations tighten failed (%s). Fallback to parent behavior.", e)
        return res
