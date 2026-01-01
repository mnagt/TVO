# -*- coding: utf-8 -*-
{
    'name': "stock_valuation",

    'summary': """
        stock_valuation""",

    'description': """
        stock_valuation. 
    """,

    'author': "Yaser Akhras",
    'website': "https://www.yaserakhras.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    
    'version': '18.0.1.0',
    'application': True,
    'license': 'AGPL-3',

    # any module necessary for this one to work correctly
    'depends': ['stock_landed_costs','base'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        "views/product_product_view.xml",
        "wizard/stock_valuation_layer_revaluation_views.xml",
    ],
}
