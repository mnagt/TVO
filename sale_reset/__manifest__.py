# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Sale Order Reset to Quotation',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Convert confirmed sale order back to quotation',
    'author': 'Yaser Akhras',
    'website': 'https://www.yaserakhras.com',
    'license': 'LGPL-3',
    'depends': [
        'sale',
    ],
    'data': [
        'views/sale_order_views.xml',
    ],
    'installable': True,
}
