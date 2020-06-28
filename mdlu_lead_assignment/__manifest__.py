# -*- coding: utf-8 -*-
{
    'name': "Lead Assignment",

    'summary': """
        An easy way to indicate (on a per team basis) how you want your new leads assigned to sales people""",

    'description': """
        Lead assignment can be an issue, especially if leads are generated from web forms.  This module allows sales managers to set their own teams patterns.
    """,

    'author': "Moddulu Solutions",
    'website': "http://www.moddulu.com",
    'license' : 'AGPL-3',
    'price': 15.00,
    'currency': 'USD',
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Sales',
    'version': '12.0.1.0',
    'images': ['static/description/banner.png',],

    # any module necessary for this one to work correctly
    'depends': ['base','crm'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/crm_team_views.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
