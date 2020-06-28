# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta, date
import math
from odoo.tools.float_utils import float_compare
from odoo.exceptions import UserError, ValidationError, AccessError

# ('', ''),

_STATES = [
    ('new', 'New'),
    ('needs_approval', 'Needs Approval'),
    ('approved', 'Approved'),
    ('checked_out', 'Checked Out'),
    ('due_soon', 'Due Soon'),
    ('over_due', 'Over Due'),
    ('returned', 'Returned'),
    ('cancelled', 'Cancelled'),
    ('renew', 'Renew Requested'),
]

_TYPES = [
    ('long', 'Long Term'),
    ('short', 'Short Term'),
]

class EquipmentLoan(models.Model):
    _name = 'equipment.loan'
    _description = 'Equipment Loan'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'resource.mixin']

    @api.model
    def _get_default_name(self):
        return self.env['ir.sequence'].next_by_code('equipment.loan')

    @api.model
    def _compute_edit_due_date(self):
        for rec in self:
            rec.edit_due_date = self.env.user.has_group('mdlu_equipment_management.group_equipment_management_manager')

    @api.model
    def _compute_edit_lines(self):
        for rec in self:
            rec.edit_lines = False
            if rec.state == 'new':
                rec.edit_lines = True
            elif rec.state == 'needs_approval' and self.env.user.has_group('mdlu_equipment_management.group_equipment_management_manager'):
                rec.edit_lines = True


    name = fields.Char(string="Reference", default=_get_default_name)
    state = fields.Selection(_STATES, string="Status", index=True, track_visibility=True, required=True, default='new', readonly=True)
    type = fields.Selection(_TYPES, string='Check Out Type', required=True, default='short', readonly=True, states={'new': [('readonly', False)]})
    user_id = fields.Many2one('res.users', string='Requsted By', domain=[('partner_id.equipment_loan_allowed', '=', True)],required=True, readonly=True, states={'new': [('readonly', False)]})
    partner_id = fields.Many2one('res.partner', string="Partner", related='user_id.partner_id')
    check_out = fields.Date(string='Date Checked Out', readonly=True)
    check_in = fields.Date(string='Date Checked In', readonly=True)
    due_date = fields.Date(string='Due Date')
    over_due_warning = fields.Boolean(string="Warning")
    over_due = fields.Boolean(string="Over Due", readonly=True)
    edit_due_date = fields.Boolean(compute='_compute_edit_due_date')
    equipment_loan_line_ids = fields.One2many('equipment.loan.line', 'loan_id', string='Items')
    edit_lines = fields.Boolean(compute='_compute_edit_lines', default=True)
    needs_repair = fields.Boolean(string='Needs Repair')
    description = fields.Html(string='Description')
    department_id = fields.Many2one('hr.department', string="Managing Department", required=True)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.user.company_id)
    renew_request = fields.Boolean(string="Renew Requested")

    @api.multi
    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        rec = super(EquipmentLoan,self).copy(default)
        for line in self.equipment_loan_line_ids:
            newline = line.copy(default)
            newline.loan_id = rec
        return rec


    @api.constrains('type', 'check_out')
    def _default_due_date(self):
        if self.check_out and not self.due_date and self.type == 'short':
            due_date = self.check_out + timedelta(days=self.company_id.equipment_checkout)
            self.due_date = due_date
            self.equipment_loan_line_ids._default_due_date(due_date)

    @api.model
    def create(self,vals):
        loan = super(EquipmentLoan, self).create(vals)
        follower_ids = loan.department_id.equipment_manager_ids.mapped('user_id').mapped('partner_id')
        follower_ids |= self.env.user.partner_id
        follower_ids |= loan.partner_id
        loan.message_subscribe(partner_ids=follower_ids.ids)
        return loan

    @api.multi
    def button_reset(self):
        #resets the request to new
        if self.is_dept_equipment_manager():
            self.write({
                'state': 'new',
                'due_date': False,
                'check_out': False,
            })
            for line in self.equipment_loan_line_ids:
                line.item_id.write({'loan_availability': 'in',})
                line.write({'state': 'new',})
        else:
            raise ValidationError(_('Only departmental equipment managers may reset equipment loans'))

    @api.multi
    def button_to_approve(self):
        #sets the request to needs approval
        for rec in self:
            rec.write({
                'state': 'needs_approval',
            })
            for line in rec.equipment_loan_line_ids:
                line.item_id.write({'loan_availability': 'req',})
                line.write({'state': 'needs_approval',})

    @api.model
    def is_dept_equipment_manager(self):
        return self.env.user in self.department_id.equipment_manager_ids.mapped('user_id') and self.env.user.has_group('mdlu_equipment_management.group_equipment_management_manager')

    @api.multi
    def button_approve(self):
        for rec in self:
            approver_ids =[1, self.env['hr.employee'].search([('user_id','=',rec.user_id.id)]).parent_id.user_id.id]
            #approves the request, ready for check outgoing
            if rec.is_dept_equipment_manager() or self.env.user.id in approver_ids:
                rec.write({
                    'state': 'approved',
                })
                for line in rec.equipment_loan_line_ids:
                    line.write({'state': 'approved',})
            else:
                raise ValidationError(_('Only departmental equipment managers may approve/deny equipment loans'))

    @api.multi
    def button_reject(self):
        #rejects the request
        if self.is_dept_equipment_manager():
            self.write({
                'state': 'rejected',
            })
            self.equipment_loan_line_ids.reject()
        else:
            raise ValidationError(_('Only departmental equipment managers may approve/deny equipment loans'))

    @api.multi
    def button_check_out(self):
        #Marks the request as checked out and all that entails
        #sets check out date
        today = fields.Date.today()
        if self.is_dept_equipment_manager():
            self.write({
                'state': 'checked_out',
                'check_out': today,
            })
            self.equipment_loan_line_ids.check_out(today)
        else:
            raise ValidationError(_('Only departmental equipment managers may check out equipment'))

    @api.multi
    def button_check_in(self):
        #checks the item(s) back in
        if self.is_dept_equipment_manager():
            self.write({
                'state': 'returned',
                'check_in': fields.Date.today(),
            })
            for line in self.equipment_loan_line_ids.filtered(lambda l: l.state == 'checked_out'):
                line.button_return()
        else:
            raise ValidationError(_('Departmental equipment managers must check in equipment'))

    @api.multi
    def button_cancelled(self):
        #cancels the request
        self.write({
            'state': 'cancelled',
        })
        self.equipment_loan_line_ids.cancel()

    @api.multi
    def button_renew(self):
        if self.is_dept_equipment_manager():
            self.write({
                'state': 'checked_out',
                'over_due_warning': False,
                'over_due': False,
                'renew_request': False,
                'due_date': self.due_date + timedelta(days=self.company_id.equipment_renewal),
            })
            self.equipment_loan_line_ids.renew_line()
            body = _('%s has been renewed and is now due back on %s by the end of the work day or contact management.') % (self.name, self.due_date.strftime('%Y-%m-%d'))
            self.message_post(body=body)
        else:
            raise ValidationError(_('Only departmental equipment managers may renew equipment'))

    @api.multi
    def check_due_date(self):
        equipment_loans = self.env['equipment.loan'].search([('state', 'in', ('checked_out', 'over_due', 'due_soon')), ('type', '=', 'short')])
        today = fields.Date.today()
        for loan in equipment_loans:
            if loan.due_date == today or today in loan.equipment_loan_line_ids.mapped('due_date'):
                body = _('%s is due today.  Please return the following equipment by the end of the day or contact management.') % (loan.name)
                for line in loan.equipment_loan_line_ids.filtered(lambda l: l.due_date == today):
                    body += _('\n%s') % (line.item_id.name)
                loan.message_post(body=body, message_type='email',**{'partner_ids': loan.partner_id.mapped('id'),})
            elif loan.due_date < today or any(today > line.due_date for line in loan.equipment_loan_line_ids):
                loan.write({
                    'over_due_warning': False,
                    'over_due': True,
                })
                if all(today > line.due_date for line in loan.equipment_loan_line_ids):
                    loan.write({'state': 'over_due'})
                loan.equipment_loan_line_ids.filtered(lambda l: l.state != 'returned').line_overdue(today)
                body = _('%s is over due.  Please return the following equipment.') % (loan.name)
                for line in loan.equipment_loan_line_ids.filtered(lambda l: l.state == 'over_due'):
                    body += _('\n%s') % (line.item_id.name)
                loan.message_post(body=body, message_type='email',**{'partner_ids': loan.partner_id.mapped('id'),})
            elif today >= (loan.due_date - timedelta(days=3)) and today <= loan.due_date or any(today >= (l.due_date - timedelta(days=3)) and today <= l.due_date for l in loan.equipment_loan_line_ids):
                loan.write({'over_due_warning': True,})
                loan.equipment_loan_line_ids._due_soon(today)
                if all(line.state == 'due_soon' for line in loan.equipment_loan_line_ids):
                    loan.write({'state': 'due_soon'})
                body = _('%s is due in three days.  Please return equipment by then or contact management.') % (loan.name)
                for line in loan.equipment_loan_line_ids.filtered(lambda l: l.state == 'due_soon'):
                    body += _('\n%s') % (line.item_id.name)
                loan.message_post(body=body, message_type='email',**{'partner_ids': loan.partner_id.mapped('id'),})



class EquipmentLoanLine(models.Model):
    _name = 'equipment.loan.line'

    name = fields.Char(related='item_id.name', string='Description')
    loan_id = fields.Many2one('equipment.loan', string='Equipment Loan')
    loan_department_id = fields.Many2one('hr.department', related='loan_id.department_id')
    check_in =  fields.Date(string='Date Checked In', readonly=True)
    state = fields.Selection(_STATES, string='Line Status', index=True, track_visibility=True, required=True, default='new', readonly=True)
    item_id = fields.Many2one('equipment.loan.item', string='Item', required=True)
    item_category = fields.Many2one('equipment.loan.category', related='item_id.categ_id', string='Item Category')
    accessory_ids = fields.Many2many('equipment.accessory', 'asset_accessory_rel', 'asset_line_id', 'accessory_id', string='Asset Accessories', domain="[('type_category','=',item_category)]")
    partner_id = fields.Many2one('res.partner', related='loan_id.partner_id', string='Partner')
    date_out = fields.Date(related='loan_id.check_out', string='Date Checked Out')
    loan_type = fields.Selection(related='loan_id.type', string='Loan Type')
    due_date = fields.Date(string='Due Date')
    equipment_requst_line = fields.Many2one('equipment.request.line', string='Equipment Request Line')

    @api.onchange('loan_department_id')
    def _get_item_domain(self):
        loan_id = self._origin.loan_id
        department_id = False
        if loan_id:
            department_id = self.env['equipment.loan'].search([('id','=',loan_id.id)]).department_id
        domain = [('loan_availability', '=', 'in'), ('category_id.department_id','=',department_id.id)]
        return domain

    def _get_default_accessories(self):
        return self.env['equipment.accessory'].search([('accessory_type.category_id','=',self.item_category.id),('default_accessory','=',True)])

    def _default_due_date(self,due_date):
        for line in self:
            line.due_date = due_date

    @api.onchange('item_id')
    def default_accessories(self):
        self.accessory_ids = self._get_default_accessories()

    @api.model
    def create(self,vals):
        res = super(EquipmentLoanLine, self).create(vals)
        res.item_id.equipment_loan_line_id = res.id
        return res

    @api.model
    def line_overdue(self, today):
        for line in self.filtered(lambda l: l.due_date < today):
            line.write({'state': 'over_due',})

    @api.model
    def _due_soon(self, today):
        for line in self.filtered(lambda l: today >= (l.due_date - timedelta(days=3)) and today <= l.due_date):
            loan.write({'state': 'due_soon'})

    @api.multi
    def button_return(self):
        today = fields.Date.today()
        if self.loan_id.is_dept_equipment_manager():
            self.item_id.write({
                'loan_availability': 'in',
                'last_check_in': today,
                'last_check_out': False,
                'repair': False,
                'equipment_loan_line_id': 0,
            })
            self.write({
                'state': 'returned',
                'check_in': today,
            })
            if not any('due_soon' == line.state for line in self.loan_id.equipment_loan_line_ids) and self.loan_id.over_due_warning:
                self.loan_id.over_due_warning = False
            if not any('over_due' == line.state for line in self.loan_id.equipment_loan_line_ids) and self.loan_id.over_due:
                self.loan_id.over_due = False
            if all('returned' == line.state for line in self.loan_id.equipment_loan_line_ids) and 'returned' != self.loan_id.state:
                self.loan_id.write({
                    'state': 'returned',
                    'check_in': fields.Date.today(),
                })
            if self.equipment_requst_line:
                self.equipment_requst_line.write({'state': 'returned',})
        else:
            raise ValidationError(_('Departmental equipment managers must check in equipment'))


    @api.model
    def check_out(self,today):
        for line in self:
            if 'new' == line.item_id.state:
                raise ValidationError(_('Please verify all items before checking them out.'))
            line.item_id.write({
                'loan_availability': 'out',
                'last_check_out': today,
                'last_check_in': False,
                'repair': line.loan_id.needs_repair,
            })
            line.write({
                'state': 'checked_out',
                'check_out': today,
            })
            line.equipment_requst_line.write({'state': 'loaned'})

    @api.multi
    def button_renew_line(self):
        if self.loan_id.is_dept_equipment_manager():
            self.renew_line()
            self.loan_id.due_date = self.due_date if self.due_date > self.loan_id.due_date else self.loan_id.due_date
            if not any('renew' == state for state in self.loan_id.equipment_loan_line_ids.mapped('state')):
                self.loan_id.write({'renew_request': False,})
            if all('checked_out' == state for state in self.loan_id.equipment_loan_line_ids.mapped('state')):
                self.loan_id.write({'state': 'checked_out','over_due':False,})
            body = _('%s has been renewed and is now due back on %s by the end of the work day or contact management.') % (self.item_id.name, self.due_date.strftime('%Y-%m-%d'))
            self.loan_id.message_post(body=body)
        else:
            raise ValidationError(_('Only departmental equipment managers may renew equipment'))


    @api.multi
    def reject_renew(self):
        today = fields.Date.today()
        if self.loan_id.is_dept_equipment_manager():
            if self.due_date < today:
                self.line_overdue(today)
            elif today >= (self.due_date - timedelta(days=3)) and today <= self.due_date:
                self._due_soon(today)
            else:
                self.write({'state': 'checked_out'})

            body = _('Your renewal request for %s has been denied.  Please return %s by end of business on %s') % (self.item_id.name, self.item_id.name, self.due_date.strftime('%Y-%m-%d'))
            subject = _('Renew request for %s has been denied.')
            self.loan_id.message_post(body=body, subject=subject, message_type='email',**{'partner_ids': self.loan_id.partner_id.mapped('id'),})
        else:
            raise ValidationError(_('Only departmental equipment managers may manage equipment'))

    @api.model
    def renew_line(self):
        today = fields.Date.today()
        for line in self.filtered(lambda l: l.state in ['checked_out', 'over_due', 'due_soon', 'renew']):
            line.item_id.write({
                'loan_availability': 'out',
            })
            line.write({
                'state': 'checked_out',
                'due_date': line.due_date + timedelta(days=line.loan_id.company_id.equipment_renewal),
            })

    @api.model
    def cancel(self):
        for line in self:
            line.item_id.write({
                'loan_availability': 'in',
                'equipment_loan_line_id': 0,
            })
            line.write({'state': 'cancelled',})
            if line.equipment_requst_line:
                line.equipment_requst_line.cancel()

    @api.model
    def reject(self):
        for line in self:
            line.item_id.write({
                'loan_availability': 'in',
                'equipment_loan_line_id': 0,
            })
            line.write({'state': 'rejected',})


class AssetAccessoriesType(models.Model):
    _name = 'equipment.accessory.type'
    _description = 'Equipment Accessory Type'

    description = fields.Char(string='Description', required=True)
    category_id = fields.Many2one('equipment.loan.category', string='Accessory Type Category', required=True)

    @api.multi
    def name_get(self):
        result = []
        for type in self:
            name = _("%s: %s") % (type.category_id.name, type.description)
            result.append((type.id, name))
        return result

class AssetAccessories(models.Model):
    _name = 'equipment.accessory'
    _description = 'Equipment Accessory'

    description = fields.Char(string='Description', required=True)
    accessory_type = fields.Many2one('equipment.accessory.type', string="Accessory Type", required=True)
    type_category = fields.Many2one('equipment.loan.category', related='accessory_type.category_id')
    asset_lines = fields.Many2many('equipment.loan.line', 'asset_accessory_rel', 'accessory_id', 'asset_line_id', string='Assets', readonly=True)
    default_accessory = fields.Boolean(string='Default Accessory')

    @api.multi
    def name_get(self):
        result = []
        for accessory in self:
            name = _("%s: %s") % (accessory.accessory_type.description, accessory.description)
            result.append((accessory.id, name))
        return result
