# -*- coding: utf-8 -*-
# Copyright 2024 Rasard
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    'name': 'TR E-Invoice PDF Attach from API',
    'version': '18.0.1.0.0',
    'summary': 'Fetches e-invoice PDF from an external API and attaches it to the chatter.',
    'author': 'Rasard',
    'category': 'Accounting/Localizations',
    'depends': [
        'account',
        'l10n_tr_nilvera_einvoice',
    ],
    'data': [
        'views/nilvera_get_einvoice_views.xml',
	'data/server_action.xml'
    ],
    'images': [
        'static/description/thumbnail.gif',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    'price':500,
    'currency':'EUR',
}
