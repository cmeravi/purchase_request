# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class StockMove(models.Model):
    _inherit = "stock.move"

    @api.constrains('picking_id')
    def check_dropship(self):
        for move in self:
            if move.picking_id.picking_type_id.name == 'Dropship':
                for move_line in move.move_line_ids:
                    move_line.qty_done = move.product_uom_qty
                move.quantity_done = move.product_uom_qty
                move.picking_id.button_validate()
