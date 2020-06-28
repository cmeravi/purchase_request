import calendar
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, Warning
from odoo.tools import float_compare, float_is_zero

_AVAILABLITY_TYPES = [
    ('out', 'Checked Out'),
    ('req', 'Requested'),
    ('in', 'Available'),
]

_VERIFICATION_STATES = [
    ('new','New Item'),
    ('verified','Verified'),
]

class EquipmentLoanItem(models.Model):
    _name = 'equipment.loan.item'
    _description = 'Loanable Item'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Item Name')
    loan_availability = fields.Selection(_AVAILABLITY_TYPES, string="Loan Status",index=True, default='in', readonly=True)
    state = fields.Selection(_VERIFICATION_STATES, string='Verification', default='new', readonly=True, track_visibility=True)
    img = fields.Binary(string="Item Image")
    barcode = fields.Char('Barcode')
    categ_id = fields.Many2one('equipment.loan.category', 'Equipment Category', required=True, related='product_id.equipment_category')
    loan_id = fields.Many2one('equipment.loan', related='equipment_loan_line_id.loan_id', track_visibility=True, readonly=True)
    last_check_out = fields.Date(string="Checked out on", readonly=True)
    last_check_in = fields.Date(string="Returned on", readonly=True)
    equipment_loan_line_id = fields.Many2one('equipment.loan.line')
    make = fields.Char(string='Make/Brand')
    model = fields.Char(string='Model')
    repair = fields.Boolean(string='Out for repair')
    serial_number = fields.Char(string='Serial Number')
    product_id = fields.Many2one('product.product', string='Product')

    @api.multi
    def action_verify(self):
        if self.env.user.has_group('mdlu_equipment_management.group_equipment_management_manager') and self.env.user in self.categ_id.department_id.equipment_manager_ids.mapped('user_id'):
            self.write({'state': 'verified',})
        else:
            raise ValidationError(_("Only %s Depertmental Equpment managers can verify this item") % (self.categ_id.department_id.name))

    @api.multi
    def action_view_loans(self):
        action = self.env.ref('mdlu_equipment_management.equipment_loan_action').read()[0]
        loan_ids = self.env['equipment.loan.line'].search([('item_id', '=', self.id)]).mapped('loan_id')
        if len(loan_ids) > 1:
            action['domain'] = [('id', 'in', loan_ids.ids)]
        elif loan_ids:
            action['views'] = [(self.env.ref('mdlu_equipment_management.mdlu_equipment_loan_management_form_view').id, 'form')]
            action['res_id'] = loan_ids.id
        return action

    @api.model
    def create(self, vals):
        rec = super(EquipmentLoanItem,self).create(vals)
        partner_ids = rec.categ_id.department_id.equipment_manager_ids.mapped('user_id').mapped('partner_id')
        rec.message_subscribe(partner_ids=partner_ids.mapped('id'))
        msg = _('Please verify %s') % (rec.name)
        subject = _('Verify %s') % (rec.name)
        rec.sudo().message_post(body=msg,subject=subject, message_type='email', **{'partner_ids': partner_ids.mapped('id'),})
        return rec


class EquipmentLoanCategory(models.Model):
    _name = 'equipment.loan.category'
    _description = 'Loanable Item Type'

    name = fields.Char(string='Category Name')
    department_id = fields.Many2one('hr.department', string="Managing Department")

class Users(models.Model):
    _inherit = 'res.users'

    #Many2many field to reference Asset Categories
    equipment_category_ids = fields.Many2many('equipment.loan.category','equipment_loan_users_rel', 'user_id', 'item_category_id', string='Managed Equipment')
