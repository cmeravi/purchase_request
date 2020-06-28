# -*- coding: utf-8 -*-
from datetime import datetime

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.addons import decimal_precision as dp
from odoo.tools.float_utils import float_compare
from odoo.exceptions import UserError, ValidationError, AccessError
from odoo.tools.misc import formatLang

class PurchaseRequest(models.Model):
    _inherit = 'purchase.request'

    @api.multi
    def button_approved(self):
        pos, po_lines = super(PurchaseRequest,self).button_approved()
        lines = self.line_ids.filtered(lambda l: l.equipment_request_line != False)
        for line in lines:
            if line.equipment_request_line:
                line.equipment_request_line.write({'state': 'purchased'})

class PurchaseRequestLine(models.Model):
    _inherit = 'purchase.request.line'

    equipment_request_line = fields.Many2one('equipment.request.line', string='Equipment Request Line')

    def get_po_vals(self, po):
        vals = super(PurchaseRequestLine,self).get_po_vals(po)
        vals['equipment_request_line'] = self.equipment_request_line.id
        return vals

    @api.multi
    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        res = super(PurchaseRequestLine,self).copy(default)
        res.equipment_request_line = self.equipment_request_line
        return res
