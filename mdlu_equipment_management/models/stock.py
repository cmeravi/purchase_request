# -*- coding: utf-8 -*-

from datetime import datetime
from dateutil import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class StockMove(models.Model):
    _inherit = 'stock.move'

    equipment_request_line = fields.Many2one('equipment.request.line', string='Equipment Request Line')

    @api.multi
    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        rec = super(StockMove,self).copy(default)
        rec.equipment_request_line = self.equipment_request_line
        return rec


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    equipment_request_line = fields.Many2one('equipment.request.line', string='Equipment Request Line', related='move_id.equipment_request_line')

    def _action_done(self):
        super(StockMoveLine,self)._action_done()
        for line in self.filtered(lambda l: l.equipment_request_line != False):
            loan_items = self.env['equipment.loan.item']
            i = 0
            while i < line.qty_done:
                vals = {
                    'name': '%s - %s - %s' % (line.equipment_request_line.name, line.picking_id.name, str(i+1)),
                    'product_id':line.product_id.id,
                }
                loan_items |= loan_items.create(vals)
                i += 1
            line.equipment_request_line.assign_item(loan_items)

class Picking(models.Model):
    _inherit = 'stock.picking'

    @api.multi
    def action_done(self):
        super_done = super(Picking,self).action_done()
        for pick in self:
            loans = pick.move_line_ids.filtered(lambda l: l.equipment_request_line != False).mapped('equipment_request_line').mapped('loan_line_ids').mapped('loan_id').filtered(lambda l: l.state == 'new')
            loans.sudo().button_to_approve()
            loans.sudo().button_approve()
        return super_done
