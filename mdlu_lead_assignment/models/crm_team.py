# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
import random

from odoo import api, fields, models, _
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import ValidationError


class Team(models.Model):
    _inherit = 'crm.team'

    override_user = fields.Boolean(string='Override Creating User',
        help="This overrides the default method of assignation.")
    lead_assignment = fields.Selection([
        ('user', 'Creating User'),
        ('crm_team_next','Next Team Member'),
        ('lowest_leads','Lowest Lead Count'),
        ('random_assignment', 'Randomly Assigned'),
    ], string='Lead Assignment Options', default='user',
        help="* Creating User - Lead is assigned to the suer who created it (this is the system default)\n"
             "* Next Team Member - Keeps track of who was previously assigned and assignes it to the next team member in line.\n"
             "* Lowest Lead Count - Assignes leads to the team member with the lowset lead count.\n"
             "* Randomly Assigned - Assigns leads completely randomly to team members.")
    next_team_member = fields.Many2one('res.users', string='Next Team Member', readonly=True)

    @api.model
    def find_next_team_member(self):
        team_members = [user for user in self.member_ids.sorted(key='id')]
        next_member = self.next_team_member if self.next_team_member else team_members[0]
        next_index = 1
        if team_members and self.next_team_member:
            current_index = team_members.index(self.next_team_member)
            next_index = current_index + 1
            if next_index > len(team_members)-1:
                next_index = 0
        self.next_team_member = team_members[next_index]
        return next_member

    @api.model
    def next_random_team_member(self,member_ids):
        members = member_ids.sorted(key='id')
        next_index = 0
        if len(members)>1:
            next_index = random.randint(0,len(members)-1)
        return members[next_index]

    @api.model
    def lowest_leads_member(self):
        next_member = self.env['res.users']
        num_leads = sorted(self.member_ids.mapped('sales_lead_count'))
        member_lowest_leads = self.member_ids.filtered(lambda m: m.sales_lead_count == num_leads[0])
        next_member = self.next_random_team_member(member_lowest_leads)
        return next_member
