# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import logging

from odoo import api, fields, models
from odoo import tools, _
from odoo.exceptions import ValidationError, AccessError
from odoo.modules.module import get_module_resource

_logger = logging.getLogger(__name__)

class Department(models.Model):
    _inherit = "hr.department"

    equipment_manager_ids = fields.Many2many('hr.employee', 'dept_asset_manager_rel', 'dept_id', 'emp_id', string='Equipment Managers', domain="[('department_id','=',id)]")

    @api.onchange('manager_id')
    def add_manager(self):
        for dept in self:
            if dept.manager_id not in dept.equipment_manager_ids:
                dept.equipment_manager_ids |= dept.manager_id
