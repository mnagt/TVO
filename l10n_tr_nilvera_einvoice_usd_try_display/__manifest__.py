{
    'name': 'Nilvera E-Invoice USD - TRY Display',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Show TRY equivalent amounts in USD invoice totals',
    'author': 'Yaser Akhras',
    'website': 'https://www.yaserakhras.com',
    'license': 'LGPL-3',
    'depends': ['l10n_tr_nilvera_einvoice_usd_tcmb'],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_tr_nilvera_einvoice_usd_try_display/static/src/components/tax_totals/tax_totals_try.js',
            'l10n_tr_nilvera_einvoice_usd_try_display/static/src/components/tax_totals/tax_totals_try.xml',
        ],
    },
    'installable': True,
}
