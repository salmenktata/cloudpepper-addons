# -*- coding: utf-8 -*-
from odoo import api, fields, models

class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    def _quelyos_set_in_steps(self, mode):
        for wh in self:
            if mode == "one_step":
                wh.reception_steps = "one_step"
            elif mode == "two_steps":
                wh.reception_steps = "two_steps"
            elif mode == "three_steps":
                wh.reception_steps = "three_steps"

    def _quelyos_set_out_steps(self, mode):
        for wh in self:
            if mode == "ship_only":
                wh.delivery_steps = "ship_only"
            elif mode == "pick_ship":
                wh.delivery_steps = "pick_ship"
            elif mode == "pick_pack_ship":
                wh.delivery_steps = "pick_pack_ship"
