# Copyright 2025 Rasard
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    'name': 'Turkey - Nilvera e-Dispatch Sender',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Localizations',
    'license': 'AGPL-3',
    'author': 'Rasard',
    'maintainer': 'Yusuf Çetin',
    'website': 'www.rasard.com',
    'price': '100.00',
    'currency': 'EUR',
    'description': """
        Send e-Dispatch XML files to Nilvera API
        - Extends l10n_tr_nilvera_edispatch module
        - Sends generated XML files to Nilvera
        - Uses company-specific API keys
    """,
    'depends': ['l10n_tr_nilvera','stock','l10n_tr_nilvera_edispatch'
                ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner.xml',
        'views/stock_picking_views.xml',
        'data/ir_cron.xml',
    ],
    'images': [
        'static/description/banner.gif',
    ],
    'installable': True,
    'auto_install': False,
}
