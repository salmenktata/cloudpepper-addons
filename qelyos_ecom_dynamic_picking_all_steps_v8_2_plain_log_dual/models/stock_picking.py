from odoo import api, models

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.model
    def action_dynamic_picking(self):
        # Logique réelle remplacée ici par un exemple
        log_msg = "[Dynamic Picking]\nSource forcée: CENT/Stock\nCritère 1 (DISPONIBLE): CENTRAL couvre toute la commande\n\nDisponibilités :\n  - CENT/Stock : 4.0\n  - CENT/Stock/Boutique Gafsa : 1.0\n  - CENT/Stock/Boutique Soukra : 1.0\n  - CENT/Stock/Boutique Sousse : 2.0"
        self.message_post(body=log_msg)
        if self.sale_id:
            self.sale_id.message_post(body=log_msg)
