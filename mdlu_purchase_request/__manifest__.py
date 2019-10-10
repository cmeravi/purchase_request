# -*- coding: utf-8 -*-
{
    'name': 'Purchase Request',
    'author': 'Moddulu Solutions',
    'version': '1.0',
    'summary': 'This module is designed to allow employees to make request items that may require purchasing approval.',
    'images': ['static/description/banner.png',],
    'price': 25.00,
    'currency': 'USD',

    'category': 'Purchases',
    'depends': [
        'purchase',
        'product',
        'purchase_stock',
    ],

    'data': [
        'security/purchase_request.xml',
        'security/ir.model.access.csv',
        'data/purchase_request_sequence.xml',
        'views/purchase_request_view.xml',
        'views/res_partner.xml',
        'views/purchase.xml',
        'views/stock_views.xml',
        'views/res_config_settings.xml',
        'views/portal_templates.xml',
    ],

    'license': 'AGPL-3',
    'installable': True
}
