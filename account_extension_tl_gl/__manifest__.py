{
    'name': 'Account Extension - TL General Ledger',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'TL Equivalent General Ledger with TL/USD toolbar',
    'author': 'Yaser Akhras',
    'website': 'https://www.yaserakhras.com',
    'license': 'LGPL-3',
    'depends': ['account_extension', 'accounting_pdf_reports'],
    'data': ['views/account_move_view.xml'],
    'assets': {
        'web.assets_backend': [
            'account_extension_tl_gl/static/src/js/general_ledger_list_controller.js',
            'account_extension_tl_gl/static/src/js/general_ledger_list_view.js',
            'account_extension_tl_gl/static/src/xml/general_ledger_list_view.xml',
        ],
    },
    'installable': True,
}