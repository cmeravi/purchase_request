# -*- coding: utf-8 -*-
from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo.addons.purchase.models.purchase import PurchaseOrder as Purchase
from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare
from odoo.exceptions import UserError, AccessError
from odoo.tools.misc import formatLang
from odoo.addons import decimal_precision as dp


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    pr_ids = fields.Many2many('purchase.request', 'purchase_request_purchase_order_rel', 'po_id', 'request_id', string="Purchase Orders")

    @api.model
    def _prepare_picking(self):
        res = super(PurchaseOrder, self)._prepare_picking()
        res.update({
            'po_id': self.id,
        })
        return res



class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    #add extra information to Purchase Order Lines to coinside with information coming form Purchase Request Lines
    web_address = fields.Html(string='Website', help='Link to the requested product for purchase')
    item_name = fields.Char(string='Line Item Name')
    pr_line_id = fields.Many2one('purchase.request.line')


    
    def cancel_line_item(self):
        for line in self:
            if line.pr_line_id:
                line.pr_line_id.do_uncancel()
                line.pr_line_id.request_id.state = 'to_approve'
                line.pr_line_id.request_id.write({'po_ids': [(3, line.order_id.id)]})
            line.sudo().unlink()

        return True
