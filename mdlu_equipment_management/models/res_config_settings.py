# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    equipment_manager = fields.Many2one('res.users', string='Default Equipment Manager', related='company_id.default_equipment_manager', readonly=False)
    equipment_renewal = fields.Integer(string='Renewal Period', related='company_id.equipment_renewal', readonly=False)
    equipment_checkout = fields.Integer(string='Initial Check Out', related='company_id.equipment_checkout', readonly=False)
