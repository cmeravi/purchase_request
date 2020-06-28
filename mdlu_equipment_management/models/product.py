# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError
from odoo.osv import expression
from odoo.addons import decimal_precision as dp
from odoo.tools import float_compare, pycompat


class ProductTemplate(models.Model):
    _inherit = "product.template"

    equipment_loan_ok = fields.Boolean(string='Can be Loaned')


class Product(models.Model):
    _inherit = "product.product"


    def _compute_items(self):
        for product in self:
            product.equipment_count = len(product.equipment_ids)

    def _compute_loanable_items(self):
        for product in self:
            product.equipment_available_count = len(product.equipment_ids.filtered(lambda self: self.loan_availability == 'in'))

    equipment_loan_ok = fields.Boolean(string='Can be Loaned', related="product_tmpl_id.equipment_loan_ok", readonly=False)
    equipment_category = fields.Many2one('equipment.loan.category', string='Loan Category')
    equipment_ids = fields.One2many('equipment.loan.item', 'product_id', string='Loanable Items')
    equipment_count = fields.Integer(string='Number of Loanable Items', compute='_compute_items')
    equipment_available_count = fields.Integer(string='Number of Items Available', compute='_compute_loanable_items')


    #define button for viewing assets
    @api.multi
    def action_view_items(self):
        action = self.env.ref('').read()[0]
        items = self.mapped('equipment_ids')
        if len(items) > 1:
            action['domain'] = [('id', 'in', items.ids)]
        elif assets:
            action['views'] = [(self.env.ref('').id, 'form')]
            action['res_id'] = items.id
        return action
