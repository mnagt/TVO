# -*- coding: utf-8 -*-
{
    'name': "partner_balance",

    'summary': """
        Partner Balance""",

    'description': """
        Partner Balance. 
    """,

    'author': "Yaser Akhras",
    'website': "https://www.yaserakhras.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    
    'version': '18.0.1.0.0',
    'application': True,
    'license': 'AGPL-3',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        "views/partner_balance_view.xml",
        

    ],

    'assets': {
        'web.assets_backend': [
            'partner_balance/static/src/scss/partner_balance.scss',
            'partner_balance/static/src/js/components/partner_balance_toolbar.js',
            'partner_balance/static/src/js/partner_balance_list_controller.js',
            'partner_balance/static/src/js/partner_balance_list_view.js',
            'partner_balance/static/src/xml/partner_balance_toolbar.xml',
            'partner_balance/static/src/xml/partner_balance_template.xml',
        ],
    },
}