{
    'name': 'Tax Balance',
    'version': '18.0.1.0.0',
    'summary': 'Tax report on customer/vendor invoices with per-tax dynamic columns.',
    'category': 'Accounting',
    'depends': ['account', 'partner_balance'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/tax_balance_view.xml',
        'views/tax_balance_line_view.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'tax_balance/static/src/scss/tax_balance.scss',
            'tax_balance/static/src/xml/tax_balance_template.xml',
            'tax_balance/static/src/js/tax_balance_list_renderer.js',
            'tax_balance/static/src/js/tax_balance_list_view.js',
        ],
    },
    'license': 'LGPL-3',
}
