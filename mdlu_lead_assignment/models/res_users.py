from odoo import api, fields, models, tools, SUPERUSER_ID, _

class Users(models.Model):
    _inherit = "res.users"

    sales_lead_count = fields.Integer(compute='_lead_count')

    @api.model
    def _lead_count(self):
        for user in self:
            user.sales_lead_count =  len(self.env['crm.lead'].search([('user_id','=',user.id)]))
