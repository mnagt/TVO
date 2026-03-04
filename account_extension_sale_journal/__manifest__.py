{
    'name': 'Account Extension - Sale Order in Journal',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Show Sales Order column and filter in Journal Items',
    'author': 'Yaser Akhras',
    'website': 'https://www.yaserakhras.com',
    'license': 'LGPL-3',
    'depends': ['account_extension', 'sale_stock'],
    'data': ['views/account_move_view.xml'],
    'post_init_hook': 'post_init_hook',
    'installable': True,
}