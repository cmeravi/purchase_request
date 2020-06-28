# -*- coding: utf-8 -*-
{
    'name': "Equipment Management",

    'summary': """
        Tracks loaning of equipment to selected users""",

    'description': """
        This module tracks the use of each piece of equipment.  It sets up a check out / check in system for each
        item that then can be assigned to an employee or location for either short or long term loan.
    """,


    'author': "Moddulu Solutions",
    'license' : 'AGPL-3',
    'website': "https://www.moddulu.com",
    'price': 70.00,
    'currency': 'EUR',
    'images': ['static/description/banner.png',],

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Accounting',
    'version': '12.0.1.0',

    # any module necessary for this one to work correctly
    'depends': [
        'base',
        'hr',
        'sale',
        'mdlu_purchase_request',
        'stock',
        'purchase',
        'product',
    ],

    # always loaded
    'data': [
        'data/equipment_sequence.xml',
        'data/ir_cron.xml',
        'security/security_view.xml',
        'security/ir.model.access.csv',
        'views/equipment_loan_views.xml',
        'views/equipment_loan_item_views.xml',
        'views/equipment_accessory_views.xml',
        'views/equipment_request_views.xml',
        'views/hr_department.xml',
        'views/templates.xml',
        'views/res_partner.xml',
        'views/product_views.xml',
        'views/res_config_settings.xml',
        'views/equipment_request_portal_templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
