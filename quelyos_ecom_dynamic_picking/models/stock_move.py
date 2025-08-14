# -*- coding: utf-8 -*-
import logging
from odoo import models, _

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_assign(self):
        """
        Hook bas-niveau : Odoo appelle _action_assign() pour faire les réservations.
        On s’assure que la stratégie Quelyos a été appliquée AVANT que la réservation ne se fasse.
        """
        # Tous les pickings sortants impactés par ces moves
        pickings = self.mapped("picking_id").filtered(lambda p: p and p.picking_type_id.code == "outgoing")
        for picking in pickings:
            try:
                # ⚠️ _quelyos_apply_strategy_if_needed NE DOIT PAS appeler super().action_assign()
                # Elle ne fait que: unreserve, reciblage, et éventuellement créer/assigner le réassort.
                picking._quelyos_apply_strategy_if_needed()
            except Exception as e:
                _logger.exception("Quelyos DP: erreur pendant pre-assign sur %s: %s", picking.name, e)
                try:
                    picking.message_post(body=_("Quelyos – Dynamic Picking: erreur avant réservation: %s") % e)
                except Exception:
                    pass

        # Laisse Odoo faire la réservation standard après application de la stratégie
        return super()._action_assign()
