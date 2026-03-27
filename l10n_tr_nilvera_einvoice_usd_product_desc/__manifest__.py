{
    'name': 'Nilvera E-Invoice USD - Product Description',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Add Nilvera product description field to products and invoice lines',
    'author': 'Yaser Akhras',
    'website': 'https://www.yaserakhras.com',
    'license': 'LGPL-3',
    'depends': ['l10n_tr_nilvera_einvoice_usd'],
    'data': [
        'views/product_views.xml',
        'views/account_move_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
}
