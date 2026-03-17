# -*- coding: utf-8 -*-
{
    'name': "Billed Product",

    'summary': """Define a product that is billed at each move""",

    'description': """This module allows you to define a product that is billed at each move.
    It is useful for tracking costs associated with internal transfers or other stock movements.""",

    'author': "Yaser Akhras",
    'website': "https://www.yaserakhras.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    
    'version': '18.0.1.0',
    'installable': True,
    'application': True,
    'license': 'AGPL-3',

    # any module necessary for this one to work correctly
    'depends': ['account', 'stock', 'purchase', 'sale', 'sale_stock', 'spreadsheet_dashboard'],

    # always loaded
    'data': [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/report_vendor_invoice_view.xml",
        "data/dashboards.xml",
    ],
    'assets': {
        'web.assets_backend': [
            'billed_product/static/src/dashboard_chart_patch.js',
        ],
    },

}
