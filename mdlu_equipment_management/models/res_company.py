# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError, UserError


class Company(models.Model):
    _inherit = "res.company"

    default_equipment_manager = fields.Many2one('res.users', string='Default Equipment Manager')
    equipment_renewal = fields.Integer(string='Renewal Period')
    equipment_checkout = fields.Integer(string='Initial Check Out')
