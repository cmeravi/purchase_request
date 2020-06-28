# -*- coding: utf-8 -*-

from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.osv import expression
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare
from odoo.exceptions import UserError, AccessError
from odoo.tools.misc import formatLang
from odoo.addons import decimal_precision as dp


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    equipment_request_line = fields.Many2one('equipment.request.line', string='Equipment Request Line')

    @api.multi
    def _prepare_stock_moves(self, picking):
        res = super(PurchaseOrderLine,self)._prepare_stock_moves(picking)
        for rec in res:
            rec['equipment_request_line'] = self.equipment_request_line.id
        return res

    @api.multi
    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        rec = supser(PurchaseOrderLine,self).copy(default)
        rec.equipment_requst_line = self.equipment_requst_line
        return rec
