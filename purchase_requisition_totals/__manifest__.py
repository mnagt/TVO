# -*- coding: utf-8 -*-
{
    'name': "Purchase Requisition Totals",

    'summary': """
        Adds tax calculation and subtotal fields to Purchase Requisition lines.""",

    'description': """
        This module extends the Purchase Requisition functionality in Odoo by:
        - Adding tax computation support to requisition lines, including:
        - Subtotal (price without tax)
        - Tax amount
        - Total (price with tax) 
    """,

    'author': "Yaser Akhras",
    'website': "https://www.yaserakhras.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/18.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list

    'version': '18.0.1.0',
    'application': False,
    'license': 'AGPL-3',

    # any module necessary for this one to work correctly
    'depends': ['purchase_requisition'],

    # always loaded
    'data': [
        "views/purchase_requisition_view.xml",
    ],
}
