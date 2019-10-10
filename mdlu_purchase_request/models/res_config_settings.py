# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pr_seq_abbr = fields.Char(string='PR Sequence Abbreviation', related='company_id.pr_seq_abbr', readonly=False)
