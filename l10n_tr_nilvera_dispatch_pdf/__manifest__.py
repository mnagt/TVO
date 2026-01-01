{
    'name': 'TR E-Dispatch PDF Attach from API',
    'version': '18.0.1.0.0',
    'summary': 'Fetches e-dispatch PDF from an external API and attaches it to the chatter.',
    'author': 'Rasard',
    'category': 'Accounting/Localizations',
    'depends': [
        'account',
        'l10n_tr_nilvera_edispatch','stock','l10n_tr_nilvera_e_dispatch_sender'
    ],
    'data': [
        'views/nilvera_get_dispatch_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    'price':500,
    'currency':'EUR',
}
