# -*- coding: utf-8 -*-

from odoo import models, fields, api, exceptions, _, SUPERUSER_ID
import logging
_logger = logging.getLogger(__name__)
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta

class Employee(models.Model):
    _inherit = 'hr.employee'

    equipment_manager_ids = fields.Many2many('hr.department', 'dept_asset_manager_rel', 'emp_id', 'dept_id', string='Equipment Managers')
