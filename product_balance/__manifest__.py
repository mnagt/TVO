{
    'name': 'Product Balance',
    'version': '18.0.1.0.0',
    'summary': 'Net Sold product quantities report from posted customer invoices and credit notes.',
    'category': 'Accounting',
    'author': 'Yaser Akhras',
    'website': 'https://www.yaserakhras.com',
    'license': 'LGPL-3',
    'depends': ['account', 'sale', 'sale_extension_team_security'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/product_balance_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'product_balance/static/src/js/product_balance_move_list_controller.js',
            'product_balance/static/src/js/product_balance_sale_list_controller.js',
        ],
    },
    'installable': True,
    'application': False,
}
