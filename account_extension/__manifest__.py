{
    'name': 'Account Extension',
    'version': '18.0.1.2.0',
    'category': 'Accounting',
    'summary': 'Accounting sequences access and feature toggles',
    'author': 'Yaser Akhras',
    'website': 'https://www.yaserakhras.com',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [
        'security/account_security.xml',
        'security/ir.model.access.csv',
        'views/ir_sequence_views.xml',
        'views/res_config_settings.xml',
    ],
    'installable': True,
}