# -*- coding: utf-8 -*-

{
    'name': 'RMA Management',
    'version': '12.0.1.0.1',
    'license': 'AGPL-3',
    'author':   'Moddulu Solutions',
    'website': 'https://moddulu.com',
    'summary': 'Return Merchandise Authorization (RMA) Management tracks and allows for both customer returns as well as vendor returns.',
    'category': 'Purchases',
    'images': ['static/description/banner.png',],
    'price': 75.00,
    'currency': 'USD',
    'depends': [
        'base',
        'purchase',
        'sale',
        'stock',
        'account',
    ],
    'data': [
        'data/ir_cron.xml',
        'security/security_view.xml',
        'security/ir.model.access.csv',
        'wizard/rma_wizard_views.xml',
        'views/stock_view.xml',
        'views/account_invoice_view.xml',
        'views/product_return_view.xml',
        'views/product_return_report.xml',
        'views/report_product_return.xml',
        'views/res_config_settings.xml',
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
        'views/rma_portal_templates.xml',
    ],
    'test': [
    ],
    'auto_install': False,
    'application': False,
    'installable': True,
}
