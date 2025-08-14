# -*- coding: utf-8 -*-
import logging
from odoo import models, _

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_assign(self):
        """
        Odoo réserve via _action_assign(). On force l'application de la stratégie
        Quelyos juste avant la réservation.
        """
        pickings = self.mapped("picking_id")
        for picking in pickings:
            try:
                # Ping de debug: prouve que ce hook s'exécute (visible dans le chatter)
                picking.sudo().message_post(
                    body=_("Quelyos – Dynamic Picking (hook _action_assign): passage avant réservation."),
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )
                picking._quelyos_apply_strategy_if_needed()
            except Exception as e:
                _logger.exception("Quelyos DP: erreur pendant pre-assign sur %s: %s", picking.name, e)
                try:
                    picking.sudo().message_post(
                        body=_("Quelyos – Dynamic Picking: erreur avant réservation: %s") % e,
                        message_type="comment",
                        subtype_xmlid="mail.mt_note",
                    )
                except Exception:
                    pass
        return super()._action_assign()
