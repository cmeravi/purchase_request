# -*- coding: utf-8 -*-
from datetime import datetime

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.addons import decimal_precision as dp
from odoo.tools.float_utils import float_compare
from odoo.exceptions import UserError, ValidationError, AccessError
from odoo.tools.misc import formatLang

_STATES = [
    ('draft', 'Draft'),
    ('to_approve', 'To be approved'),
    ('partial_approved', 'Partially Approved'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
    ('cancelled', 'Cancelled'),
    ('ordered', 'Ordered')
]


class PurchaseRequest(models.Model):
    _name = 'purchase.request'
    _description = 'Purchase Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    #Add purchase order tracking to purchase request
    @api.multi
    def _count_pos(self):
        for req in self:
            req.po_count = len(req.po_ids)

    @api.model
    def _get_default_name(self):
        name = self.name
        if not name:
            name = self.env['ir.sequence'].next_by_code('purchase.request')
        if self.company_id.pr_seq_abbr:
            name = "%s-%s" % (self.company_id.pr_seq_abbr,name)
        return name

    @api.model
    def _default_picking_type(self):
        type_obj = self.env['stock.picking.type']
        company_id = self.env.context.get('company_id') or self.env.user.company_id.id
        types = type_obj.search([('code', '=', 'incoming'),('warehouse_id.company_id', '=', company_id)])
        if not types:
            types = type_obj.search([('code', '=', 'incoming'),('warehouse_id', '=', False)])
        return types[:1]

    @api.multi
    @api.depends('state')
    def _compute_is_editable(self):
        for rec in self:
            if rec.state in ('to_approve', 'approved', 'rejected'):
                rec.is_editable = False
            else:
                rec.is_editable = True


    name = fields.Char('Request Reference', size=32, required=True, default=_get_default_name, track_visibility='onchange')
    origin = fields.Char('Source Document', size=32)
    date_start = fields.Date('Creation date', help="Date when the user initiated the request.", default=fields.Date.context_today, track_visibility='onchange')
    user_id = fields.Many2one('res.users', 'Requested by', track_visibility='onchange', domain=[('partner_id.purchase_request_allowed','=',True)], default=lambda self: self.env.user)
    partner_id = fields.Many2one('res.partner', 'Related Partner', related='user_id.partner_id')
    assigned_to = fields.Many2one('res.users', 'Approver', track_visibility='onchange')
    description = fields.Text('Description')
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self:self.env.user.company_id, track_visibility='onchange')
    line_ids = fields.One2many('purchase.request.line', 'request_id', 'Products to Purchase', readonly=False, copy=True, track_visibility='onchange')
    state = fields.Selection(selection=_STATES, string='Status', index=True, track_visibility=True, required=True, copy=False, default='draft')
    is_editable = fields.Boolean(string="Is editable", compute="_compute_is_editable", readonly=True)
    picking_type_id = fields.Many2one('stock.picking.type', 'Picking Type', required=True, default=_default_picking_type)
    po_ids = fields.Many2many('purchase.order', 'purchase_request_purchase_order_rel', 'request_id', 'po_id', string="Purchase Orders")
    po_count = fields.Integer(compute='_count_pos')

    @api.multi
    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = dict(default or {})
        self.ensure_one()
        default.update({
            'state': 'draft',
            'name': self._get_default_name(),
        })
        rec = super(PurchaseRequest, self).copy(default)
        for line in self.line_ids:
            line.copy()
            line.request_id = rec
        return rec

    @api.model
    def create(self, vals):
        request = super(PurchaseRequest, self).create(vals)
        request.name = request._get_default_name()
        follower_ids = []
        if vals.get('assigned_to'):
            follower_ids.append(self.env['res.users'].search([('id', '=', vals['assigned_to'])], limit=1).partner_id.id)
        if request.line_ids:
            follower_ids.extend(request.line_ids.mapped('second_approver.partner_id.id'))
        if follower_ids:
            request.message_subscribe(partner_ids=follower_ids)
        return request

    @api.multi
    def write(self, vals):
        res = super(PurchaseRequest, self).write(vals)
        for request in self:
            message_partner_ids = request.message_partner_ids.mapped('id')
            follower_ids = []
            if vals.get('assigned_to'):
                follower_ids.append(self.env['res.users'].search([('id', '=', vals['assigned_to'])], limit=1).partner_id.id)
            if request.line_ids:
                follower_ids.extend(request.line_ids.mapped('second_approver.partner_id.id'))
            follower_ids = [x for x in follower_ids if x not in message_partner_ids]
            if follower_ids:
                request.message_subscribe(partner_ids=follower_ids)
        return res

    #define reset button
    @api.multi
    def button_draft(self):
        for rec in self:
            rec.state = 'draft'
            rec.line_ids.do_uncancel()
        return True

    #define request for approval button
    @api.multi
    def button_to_approve(self):
        for rec in self:
            rec.state = 'to_approve'
        return True

    #define approved/ordered button this button checks state of PR line items for ordering.
    @api.multi
    def button_approved(self):
        #create lists of purchase orders and po lines to return at the end of the method
        pos = self.env['purchase.order']
        po_lines = self.env['purchase.order.line']
        for rec in self:
            for line in rec.line_ids:
                #check each line for individaul line approval
                if line.state == 'approved':
                    #check to see if there is already an open PO for the related vendor
                    po = self.env['purchase.order'].search([('state', '=', 'draft'),('partner_id', '=', line.vendor_id.id), ('partner_ref', '=', False)], limit=1)
                    #if there isn't an open PO for the related vendor, create a new PO
                    if not po:
                        po_vals = {
                            'origin': rec.name,
                            'partner_id': line.vendor_id.id,
                            'state': 'draft',
                            'company_id': rec.company_id.id,
                        }
                        po = self.env['purchase.order'].create(po_vals)
                    else:
                        #if there is an open po, append the origin with the current PR name
                        po_origins = po.origin.split(',') if po.origin else False
                        if po_origins and rec.name not in po_origins:
                            po.origin = po.origin + ", " + rec.name
                        else:
                            po.origin = rec.name

                    #Look to see if the line item is already on the PO
                    new_po_line = self.env['purchase.order.line'].search([('order_id', '=', po.id), ('product_id', '=', line.product_id.id), ('name', '=', rec.name)])
                    #if not already on the po, add the line item to the po
                    if not new_po_line:
                        po_line_vals = line.get_po_vals(po)
                        new_po_line = self.env['purchase.order.line'].create(po_line_vals)
                        po_lines |= new_po_line
                    #Change the Line state to Ordered which is a finished state.
                    line.state = 'ordered'
                    #assign the current PO to the purchase request line for easy reference.
                    line.purchase_order_id = po

                    pos |= po
                    #assign the PO to the PR list for easy reference.
                    rec.po_ids |= po
            #check to see if all line items have been ordered, rejected, or cancelled on the PR, if so, finish order, if not leave open for further processing.
            rec.state = 'partial_approved'
            rec_lines = self.env['purchase.request.line'].search([('request_id', '=', rec.id), ('state', 'not in', ['ordered', 'cancelled','rejected'])])
            if not rec_lines:
                rec.state = 'approved'
        return pos, po_lines

        #create button to view POs
    @api.multi
    def action_view_po(self):
        pos = self.mapped('po_ids')
        action = self.env.ref('mdlu_purchase_request.pr_po_tree').read()[0]
        if len(pos) > 1:
            action['domain'] = [('id', 'in', pos.ids)]
        elif len(pos) == 1:
            action['views'] = [(self.env.ref('purchase.purchase_order_form').id, 'form')]
            action['res_id'] = pos.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    #create reject PR button
    @api.multi
    def button_rejected(self):
        for rec in self:
            rec.state = 'rejected'
            rec.line_ids.button_rejected()
        return True

    #create Cancel PR button
    @api.multi
    def button_cancelled(self):
        for rec in self:
            rec.state = 'cancelled'
            rec.line_ids.do_cancel()
        return True

    @api.multi
    def check_auto_reject(self):
        """When all lines are cancelled the purchase request should be
        auto-rejected."""
        for pr in self:
            if not pr.line_ids.filtered(lambda l: l.cancelled is False):
                pr.write({'state': 'rejected'})

class PurchaseRequestLine(models.Model):

    _name = "purchase.request.line"
    _description = "Purchase Request Line"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.multi
    @api.depends('product_id', 'name', 'product_uom_id', 'product_qty',
                 'analytic_account_id', 'date_required', 'specifications')
    def _compute_is_editable(self):
        for rec in self:
            if rec.request_id.state in ('to_approve', 'approved', 'rejected', 'cancelled'):
                rec.is_editable = False
            else:
                rec.is_editable = True

    @api.multi
    @api.depends('product_id', 'name', 'product_uom_id', 'product_qty',
                 'analytic_account_id', 'date_required', 'specifications')
    def _compute_can_edit(self):
        for rec in self:
            if rec.request_id.state in ('approved', 'rejected', 'cancelled'):
                rec.can_edit = False
            else:
                rec.can_edit = True

    @api.multi
    @api.depends('product_id', 'name', 'product_uom_id', 'product_qty',
                 'analytic_account_id', 'date_required', 'specifications')
    def _compute_additional_approval(self):
        for rec in self:
            if rec.request_id.state in ('draft', 'approved', 'rejected', 'cancelled'):
                rec.additional_approval = False
            else:
                rec.additional_approval = True

    @api.multi
    def _compute_supplier_id(self):
        for rec in self:
            if not rec.supplier_id:
                if rec.product_id:
                    if rec.product_id.seller_ids:
                        rec.supplier_id = rec.product_id.variant_seller_ids[0].name

    @api.onchange('product_id')
    @api.depends('product_id')
    def _default_vendor(self):
        for line in self:
            line.vendor_id = line.supplier_id


    @api.onchange('product_id')
    @api.depends('product_id')
    def _default_product_uom(self):
        for line in self:
            line.product_uom_id = line.product_id.uom_id

    @api.onchange('product_id')
    @api.depends('product_id')
    def _calculate_default_price(self):
        for line in self:
            price_unit = 0.00
            product = self.product_id
            vendor = line.supplier_id
            if line.vendor_id:
                vendor = line.vendor_id
            if line.product_id.variant_seller_ids:
                seller_product_price = self.env['product.supplierinfo'].search([('product_tmpl_id', '=', product.product_tmpl_id.id), ('name','=', vendor.id), ('product_id', '=', product.id)], limit=1).price
                seller_price = self.env['product.supplierinfo'].search([('product_tmpl_id', '=', product.product_tmpl_id.id), ('name','=', vendor.id), ('product_id', '=', False)], limit=1).price
                if seller_product_price:
                    price_unit = seller_product_price
                elif seller_price:
                    price_unit = seller_price
            line.price_unit = price_unit

    product_id = fields.Many2one('product.product', 'Product', domain=[('purchase_ok', '=', True)], track_visibility='onchange', required=True)
    name = fields.Char('Description', size=256, track_visibility='onchange', required=True)
    product_uom_id = fields.Many2one('uom.uom', string='Product Unit of Measure', default=_default_product_uom, track_visibility='onchange', store=True)
    product_qty = fields.Float('Quantity', track_visibility='onchange', digits=dp.get_precision('Product Unit of Measure'))
    request_id = fields.Many2one('purchase.request', 'Purchase Request', ondelete='cascade', readonly=True)
    company_id = fields.Many2one('res.company', related='request_id.company_id', string='Company', store=True, readonly=True)
    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account', track_visibility='onchange')
    user_id = fields.Many2one('res.users', related='request_id.user_id', string='Requested by', store=True, readonly=True)
    assigned_to = fields.Many2one('res.users', related='request_id.assigned_to', string='Assigned to', store=True, readonly=True)
    date_start = fields.Date(related='request_id.date_start', string='Request Date', readonly=True, store=True)
    description = fields.Text(related='request_id.description', string='Request Description', readonly=True, store=True)
    origin = fields.Char(related='request_id.origin', size=32, string='Source Document', readonly=True, store=True)
    date_required = fields.Date(string='Required by Date', required=True, track_visibility='onchange', default=fields.Date.context_today)
    is_editable = fields.Boolean(string='Is editable', compute="_compute_is_editable", readonly=True)
    can_edit = fields.Boolean(string='Can edit', compute="_compute_can_edit", readonly=True)
    specifications = fields.Text(string='Specifications')
    request_state = fields.Selection(string='Request state', readonly=True, related='request_id.state', selection=_STATES, store=True)
    supplier_id = fields.Many2one('res.partner', string='Preferred supplier', compute="_compute_supplier_id")
    vendor_id = fields.Many2one('res.partner', string="Vendor", default=_default_vendor, required=True)
    cancelled = fields.Boolean( string="Cancelled", readonly=True, default=False, copy=False)
    web_address = fields.Char(string='Website Link', help='Link to the requested product for purchase')
    purchase_order_id = fields.Many2one('purchase.order', string='Purchase Order', readonly=True)
    po_state = fields.Selection(related='purchase_order_id.state', string='PO Status')
    state = fields.Selection(string='Status', readonly=True, selection=_STATES, default='draft', track_visibility=True)
    second_approver = fields.Many2one('res.users', string='Second Approval', domain="[('share', '=', False)]")
    additional_approval = fields.Boolean(string='Needs Additional Approval', compute="_compute_additional_approval", readonly=True)
    reason = fields.Char(string="Reason Requested", required=True)
    price_unit = fields.Float(string='Unit Price', digits=dp.get_precision('Product Price'), default=_calculate_default_price)

    #Complete fields with product is entered
    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id.id
            self.product_qty = 1


    #Resets the vendor field to the default supplier
    @api.multi
    def button_reset_vendor(self):
        self.vendor_id = self.supplier_id

    #whenever a pr line status is changed, log in pr chatter
    @api.constrains('state')
    def send_msg(self):
        for line in self:
            partner = self.env.user.partner_id
            message = "%s moved to Status: %s" % (line.product_id.name, dict(_STATES)[line.state])
            line.request_id.sudo().message_post(body=message, message_type='notification', author_id=partner.id)
            #when a pr line has a secondary approver notify the approver when they need to approve the item.
            if line.second_approver and line.state == 'to_approve':
                line_message = line.second_approver.partner_id.name + " this item requires secondary approval."
                partner_ids = [line.second_approver.partner_id.id]
                line.sudo().message_post(body=line_message, message_type='comment', partner_ids=partner_ids)


    #define button for cancelling a pr line
    @api.multi
    def button_cancel(self):
        for rec in self:
            rec.do_cancel()
        return True

    #define button for approving a pr line
    @api.multi
    def button_approve(self):
        for rec in self:
            if rec.cancelled:
                rec.do_uncancel()
            #check for a second approver after initial approval, if there is a second approver, set to 'To be approved'
            if rec.second_approver and rec.state != 'to_approve':
                rec.state = 'to_approve'
            #check for a second approver on pr line.  IF there is one and the current user is noth that person, notify user of second approval
            elif rec.second_approver and rec.second_approver.id != self.env.user.id:
                variable_attributes = rec.product_id.attribute_line_ids.filtered(lambda l: len(l.value_ids) > 1).mapped('attribute_id')
                variant = rec.product_id.attribute_value_ids._variant_name(variable_attributes)
                product_name = variant and "%s (%s)" % (rec.product_id.name, variant) or rec.product_id.name
                raise ValidationError('%s can only be approved by %s' % (product_name, rec.second_approver.name))
            #if there is not second approver or the current user is the second approver set state to approved
            else:
                rec.state = 'approved'
        return True

    #define button for rejecting currend PR line
    @api.multi
    def button_rejected(self):
        for rec in self:
            rec.state = 'rejected'
            rec.cancelled = True
        return True

    #define button for resetting unfinished PR line
    @api.multi
    def button_reset(self):
        for rec in self:
            rec.do_uncancel()
        return True

    @api.multi
    def do_cancel(self):
        """Actions to perform when cancelling a purchase request line."""
        self.write({'cancelled': True, 'state': 'cancelled'})
        if all(c == 'cancelled' for c in self.request_id.line_ids.mapped('state')):
            self.request_id.write({'state': 'cancelled',})

    @api.multi
    def do_uncancel(self):
        """Actions to perform when uncancelling a purchase request line."""
        self.write({'cancelled': False, 'state': 'draft'})

    @api.multi
    def write(self, vals):
        res = super(PurchaseRequestLine, self).write(vals)
        if vals.get('cancelled'):
            requests = self.mapped('request_id')
            requests.check_auto_reject()
        return res

    def get_po_vals(self, po):
        return {
            'name': self.name,
            'order_id': po.id,
            'product_id': self.product_id.id,
            'product_qty': self.product_qty,
            'price_unit': self.product_id.price,
            'product_uom': self.product_id.uom_id.id,
            'date_planned': po.date_order,
            'web_address': self.web_address,
            'item_name': self.name,
            'pr_line_id': self.id,
            'price_unit': self.price_unit,
        }
