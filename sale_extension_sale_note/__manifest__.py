# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Sale Extension - Sale Note',
    'version': '18.0.1.1.0',
    'category': 'Sales',
    'summary': 'Sale Note with Bank Account Display',
    'description': """
    Sale Note Module

    Features:
    - Automatic note generation with exchange rates
    - Bank account selection for quotations/proforma
    - Bank account display in PDF reports
    """,
    'author': 'Yaser Akhras',
    'website': 'https://www.yaserakhras.com',
    'license': 'LGPL-3',
    'depends': [
        'sale_extension',
        'tcmb',
    ],
    'data': [
        'views/sale_order_views.xml',
        'report/sale_order_report_templates.xml',
    ],
    'installable': True,
}
