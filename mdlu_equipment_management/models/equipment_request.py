# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta, date
import math
from odoo.addons import decimal_precision as dp
from odoo.tools.float_utils import float_compare
from odoo.exceptions import UserError, ValidationError, AccessError


# ('', ''),

_STATES = [
    ('draft', 'New'),
    ('needs_approval', 'Needs Approval'),
    ('partial_approve','Partial Approval'),
    ('approved', 'Approved'),
    ('loaned', 'Loaned'),
    ('loan_requested', 'Loan Requested'),
    ('purchase_requested', 'Purchase Requested'),
    ('purchased', 'Purchased'),
    ('received', 'Received'),
    ('returned','Returned'),
    ('cancelled', 'Cancelled'),
    ('rejected', 'Rejected'),
]

_TYPES = [
    ('long', 'Long Term'),
    ('short', 'Short Term'),
]


class EquipmentRequest(models.Model):
    _name = 'equipment.request'
    _description = 'Equipment Request'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'resource.mixin']

    def _get_default_name(self):
        return self.env['ir.sequence'].next_by_code('equipment.request')

    @api.model
    def _get_default_manager(self):
        assigned_to = self.partner_id.equipment_manager
        if not assigned_to:
            assigned_to = self.company_id.default_equipment_manager
        return assigned_to

    @api.onchange('user_id')
    def get_default_manager(self):
        for rec in self:
            rec.assigned_to = rec._get_default_manager()

    def _compute_loans(self):
        for rec in self:
            rec.loan_count = len(rec.request_line_ids.mapped('loan_line_ids').mapped('loan_id'))

    def _compute_prs(self):
        for rec in self:
            rec.pr_count = len(rec.request_line_ids.mapped('purchase_request_id'))

    @api.model
    def is_dept_equipment_manager(self):
        return self.env.user == self.assigned_to and self.env.user.has_group('mdlu_equipment_management.group_equipment_management_manager')

    name = fields.Char(string='Number', default=_get_default_name, required=True, readonly=True, states={'draft': [('readonly', False)]})
    request_date = fields.Date(string='Date Requested', readonly=True)
    state = fields.Selection(_STATES, string='Status', index=True, track_visibility=True, default='draft', readonly=True)
    user_id = fields.Many2one('res.users', string='Requested By', domain=[('partner_id.equipment_loan_allowed','=',True)], required=True)
    partner_id = fields.Many2one('res.partner', related='user_id.partner_id')
    assigned_to = fields.Many2one('res.users', 'Approver', track_visibility='onchange', default=_get_default_manager)
    request_line_ids = fields.One2many('equipment.request.line', 'request_id', 'Request Lines')
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self:self.env.user.company_id, track_visibility='onchange')
    loan_count = fields.Integer(string='Loans', compute=_compute_loans)
    pr_count = fields.Integer(string='Purchase Requests', compute=_compute_prs)

    @api.multi
    def action_request_approval(self):
        self.write({
            'state':'needs_approval',
            'request_date': date.today(),
        })
        self.request_line_ids.action_request_approval()

    @api.multi
    def action_approve(self):
        for req in self:
            approved_lines = req.request_line_ids.filtered(lambda l: 'approved' == l.state)
            for line in approved_lines:
                loan_qty = 0
                if not line.force_purchase:
                    loan_qty = line.product_qty if line.product_qty <= line.product_id.equipment_available_count else line.product_id.equipment_available_count
                pr_qty = line.product_qty - loan_qty
                if loan_qty:
                    department_id = line.product_id.equipment_ids.mapped('categ_id')[0].department_id
                    loan = self.env['equipment.loan'].search([('partner_id','=', req.partner_id.id),('state','=','new'),('type','=',line.type),('department_id','=',department_id.id)], limit=1)
                    #If no new loans of appropriate type create new loan
                    if not loan:
                        name = self.env['equipment.loan']._get_default_name()
                        loan = self.env['equipment.loan'].create({
                            'name': name,
                            'type': line.type,
                            'user_id': req.user_id.id,
                            'department_id':department_id.id,
                        })
                    else:
                        loan = loan[0]
                    line.loan_item(loan_qty,loan)
                    if loan_qty < line.product_qty:
                        line.write({'product_qty': loan_qty,})
                if pr_qty:
                    pr = req.partner_id.pr_ids.filtered(lambda r: 'draft' == r.state)
                    if not pr:
                        pr = self.env['purchase.request'].create({
                            'user_id': req.user_id.id,
                            'company_id': req.company_id.id,
                        })
                    else:
                        pr = pr[0]
                    line.purchase_request_item(pr_qty,pr)
            if 'needs_approval' not in req.request_line_ids.mapped('state'):
                req.write({'state': 'approved'})
            else:
                req.write({'state': 'partial_approve'})

            req.request_line_ids.mapped('loan_id').button_to_approve()
            req.request_line_ids.mapped('loan_id').sudo().button_approve()
            req.request_line_ids.mapped('purchase_request_id').button_to_approve()


    @api.multi
    def action_cancel(self):
        self.write({'state':'cancelled',})
        self.request_line_ids.action_cancel()

    @api.multi
    def action_reject(self):
        self.write({'state':'rejected',})
        self.request_line_ids.action_reject()

    @api.multi
    def action_draft(self):
        for rec in self:
            rec.write({'state': 'draft',})
            rec.request_line_ids.action_draft()

    @api.multi
    def check_auto_complete(self):
        """When all lines are cancelled or rejected the purchase request should be
        auto-rejected."""
        for req in self:
            line_states = req.request_line_ids.mapped('state')
            if len(line_states) == 1:
                if 'rejected' == line_states[0]:
                    req.write({'state': 'rejected',})
                elif 'cancelled' == line_states[0]:
                    req.write({'state': 'cancelled',})

    @api.multi
    def action_view_loans(self):
        loans = self.request_line_ids.mapped('loan_line_ids').mapped('loan_id')
        action = self.env.ref('mdlu_equipment_management.equipment_loan_action').read()[0]
        if len(loans) > 1:
            action['domain'] = [('id','in', loans.ids)]
        elif len(loans) == 1:
            action['views'] = [(self.env.ref('mdlu_equipment_management.mdlu_equipment_loan_management_form_view').id, 'form')]
            action['res_id'] = loans.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.multi
    def action_view_prs(self):
        prs = self.request_line_ids.mapped('purchase_request_id')
        action = self.env.ref('mdlu_purchase_request.purchase_request_form_action').read()[0]
        if len(prs) > 1:
            action['domain'] = [('id','in', prs.ids)]
        elif len(prs) == 1:
            action['views'] = [(self.env.ref('mdlu_purchase_request.view_purchase_request_form').id, 'form')]
            action['res_id'] = prs.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

class EquipmentRequestLine(models.Model):
    _name = 'equipment.request.line'
    _description = 'Equipment Request Line'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'resource.mixin']

    @api.onchange('product_id')
    def _default_vendor(self):
        if self._origin.product_id.seller_ids:
            self.vendor_id = self._origin.product_id.seller_ids[0].name

    def _compute_loan(self):
        for rec in self:
            loans = rec.loan_line_ids.mapped('loan_id')
            if len(loans) == 1:
                rec.loan_id = loans
            else:
                rec.loan_id = self.env['equipment.loan']

    def _compute_pr(self):
        for rec in self:
            pr_ids = rec.pr_line_ids.mapped('request_id')
            if len(pr_ids) == 1:
                rec.purchase_request_id = pr_ids
            else:
                rec.purchase_request_id = self.env['purchase.request']

    def _compute_move_lines(self):
        for rec in self:
            rec.move_line_count = len(rec.move_line_ids)

    def _compute_loan_lines(self):
        for rec in self:
            rec.loan_line_count = len(rec.loan_line_ids)

    #General Fields
    product_id = fields.Many2one('product.product', 'Item', domain=[('equipment_loan_ok','=',True)], required=True)
    request_id = fields.Many2one('equipment.request', 'Equipment Request')
    company_id = fields.Many2one('res.company', related='request_id.company_id', string='Company', store=True, readonly=True)
    state = fields.Selection(_STATES, string='Status', index=True, track_visibility=True, required=True, default='draft', readonly=True)
    request_state = fields.Selection(_STATES, string='Request Status', index=True, related='request_id.state')
    request_assigned_to = fields.Many2one('res.users', 'Assigned To', related="request_id.assigned_to")
    requested_by = fields.Many2one('res.users', 'Requested By', related="request_id.user_id")
    force_purchase = fields.Boolean(string='Purchase')

    # Purchase Request fields
    purchase_request_id = fields.Many2one('purchase.request', 'Purchase Request', compute=_compute_pr)
    pr_line_ids = fields.One2many('purchase.request.line', 'equipment_request_line', 'PR Lines', readonly=True)
    pr_state = fields.Selection(related='purchase_request_id.state', string='PR Status')
    vendor_id = fields.Many2one('res.partner', string='Vendor', required=True)
    name = fields.Char('Description', required=True)
    product_uom_id = fields.Many2one('uom.uom', string='Product Unit of Measure', related='product_id.uom_id')
    product_qty = fields.Float('Quantity', track_visibility='onchange', digits=dp.get_precision('Product Unit of Measure'))
    web_address = fields.Char(string='Website Link', help='Link to the requested product for purchase')
    reason = fields.Char(string='Reason Requested', required=True)
    price_unit = fields.Float(string='Unit Price', digits=dp.get_precision('Product Price'))
    specifications = fields.Text(string='Specifications')
    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account', track_visibility='onchange')

    #Stock Transfer Fields
    move_line_ids = fields.One2many('stock.move.line', 'equipment_request_line', 'Stock Moves', readonly=True)
    move_line_count = fields.Integer(compute=_compute_move_lines)

    # Equipment Loan fields
    loan_id = fields.Many2one('equipment.loan', 'Loan', compute=_compute_loan, readonly=True)
    loan_state = fields.Selection(related='loan_id.state', string='Loan State')
    loan_line_ids = fields.One2many('equipment.loan.line', 'equipment_requst_line', 'Loan Lines', readonly=True)
    loan_line_count = fields.Integer(compute=_compute_loan_lines)
    type = fields.Selection(_TYPES, string='Loan Type', required=True, default='short')


    @api.multi
    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = dict(default or {})
        self.ensure_one()
        default.update({
            'state': 'draft',
        })
        rec = super(EquipmentRequestLine, self).copy(default)
        return rec


    @api.multi
    def loan_item(self,qty,loan):
        loan_lines = self.env['equipment.request.line']
        item_ids = self.product_id.equipment_ids.filtered(lambda self: self.loan_availability == 'in')
        i = 0
        while i < qty:
            loan_line_dict = {
                'loan_id':loan.id,
                'item_id':item_ids[i].id,
                'equipment_requst_line': self.id
            }
            self.env['equipment.loan.line'].create(loan_line_dict)
            i += 1
        self.write({'state': 'loan_requested',})

    @api.multi
    def purchase_request_item(self,qty,pr):
        pr_line_dict = {
            'request_id': pr.id,
            'product_id': self.product_id.id,
            'name':self.name,
            'product_qty':qty,
            'product_uom_id':self.product_uom_id.id,
            'vendor_id':self.vendor_id.id,
            'price_unit':self.price_unit,
            'web_address':self.web_address,
            'reason':self.reason,
            'specifications':self.specifications,
            'analytic_account_id':self.analytic_account_id.id,
            'equipment_request_line':self.id,
        }
        pr_line = self.env['purchase.request.line'].create(pr_line_dict)
        self.write({'state': 'purchase_requested',})


    def assign_item(self,item_ids):
        loans = self.env['equipment.loan']
        for item_id in item_ids:
            department_id = item_id.product_id.equipment_ids.mapped('categ_id')[0].department_id
            loan = loans.filtered(lambda self: self.department_id == department_id)
            loan = loan if loan else self.env['equipment.loan'].search([('partner_id','=', self.request_id.partner_id.id),('state','=','new'),('type','=',self.type),('department_id','=',department_id.id)])
            if not loan:
                name = self.env['equipment.loan']._get_default_name()
                loan = loan.create({
                    'user_id': self.requested_by.id,
                    'type': self.type,
                    'name': name,
                    'partner_id': self.request_id.partner_id.id,
                    'department_id':department_id.id,
                })

            vals = {
                'loan_id':loan[0].id,
                'item_id':item_id.id,
                'equipment_requst_line': self.id
            }
            new_line = self.env['equipment.loan.line'].create(vals)
            new_line.accessory_ids = new_line._get_default_accessories()
            loans |= loan


    #create button to view loan_line_ids
    @api.multi
    def action_view_loan(self):
        action = self.env.ref('mdlu_purchase_request.mdlu_equipment_loan_management_form_view').read()[0]
        action['views'] = [(self.env.ref('purchase.purchase_order_form').id, 'form')]
        action['res_id'] = self.loan_id.id
        return action

    #create button to view PRs
    @api.multi
    def action_view_pr(self):
        action = self.env.ref('mdlu_purchase_request.view_purchase_request_form').read()[0]
        action['views'] = [(self.env.ref('purchase.purchase_order_form').id, 'form')]
        action['res_id'] = self.purchase_request_id.id
        return action


    @api.multi
    def action_request_approval(self):
        for line in self:
            line.write({'state':'needs_approval',})
            partner_id = line.request_id.assigned_to.partner_id.id
            line.message_subscribe(partner_ids=[partner_id])
            msg = _('%s on %s requres approval') % (line.name, line.request_id.name)
            subject = _('Approve Item(s)')
            line.sudo().message_post(body=msg,subject=subject, message_type='email', **{'partner_ids': [partner_id],})

    @api.multi
    def action_approve(self):
        if self.request_id.is_dept_equipment_manager():
            self.write({'state':'approved'})
        else:
            raise ValidationError(_('Only the assigned approver may approve/deny equipment requests.'))


    @api.multi
    def action_cancel(self):
        for line in self.filtered(lambda l: l.state != 'cancelled'):
            line.cancel()
            if line.pr_line_ids:
                line.pr_line_ids.button_cancel()
            if line.loan_line_ids:
                line.loan_line_ids.cancel()
        if all(l.state == 'cancelled' for l in self[0].request_id.request_line_ids):
            self[0].request_id.write({'state':'cancelled',})

    def cancel(self):
        for line in self:
            line.write({'state':'cancelled',})

    @api.multi
    def action_reject(self):
        for line in self:
            line.reject()
            if line.pr_line_ids:
                line.pr_line_ids.button_rejected()
            if line.loan_line_ids:
                line.loan_line_ids.reject()

    def reject(self):
        for line in self:
            line.write({'state':'rejected',})

    @api.multi
    def action_draft(self):
        for rec in self:
            rec.write({'state':'draft',})
