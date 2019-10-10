# -*- coding: utf-8 -*-

from odoo import api, fields, models


class Picking(models.Model):
    _inherit = "stock.picking"

    po_id = fields.Many2one('purchase.order', string='PO #')
    partner_ref = fields.Char(related='po_id.partner_ref', string='Vendor Reference')
