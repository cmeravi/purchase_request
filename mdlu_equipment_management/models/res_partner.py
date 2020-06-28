# coding: utf-8

from odoo import api, fields, models, _

class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def default_manager(self):
        equipment_manager_id = self.company_id.default_equipment_manager
        employee_id = self.env['hr.employee'].search([('user_id.partner_id','=', self.id)])
        if employee_id:
            if employee_id.parent_id:
                equipment_manager_id = employee_id.parent_id.user_id
            elif employee_id.department_id:
                equipment_manager_id = employee_id.department_id.manager_id.user_id
        return equipment_manager_id

    @api.model
    def _default_equipment_manager(self):
        return self.default_manager()

    @api.onchange('equipment_loan_allowed')
    def check_equipment_manager(self):
        if not self._origin.equipment_manager:
            self.equipment_manager = self._origin.default_manager()

    equipment_loan_allowed = fields.Boolean(string='Can Borrow Equipment')
    loaned_equipment_ids = fields.One2many('equipment.loan.line', 'partner_id', string="Equipment on loan", domain=[('state','in',['needs_approval','approved','checked_out','over_due'])], readonly=True)
    equipment_manager = fields.Many2one('res.users', string='Equipment Manager', default=_default_equipment_manager)
