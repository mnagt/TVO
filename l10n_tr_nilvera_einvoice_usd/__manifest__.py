{
    "name": "Nilvera - USD",
    "version": "18.0.1.0.2",
    "author": "Yaser Akhras",
    "website": "https://yaserakhras.com",
    "license": "LGPL-3",
    "category": "Accounting",
    "summary": "Modify Nilvera E-invoice Module to work as well for company which its base currency is USD.",
    "depends": ["l10n_tr_nilvera_einvoice_extended", "tcmb", "l10n_tr_nilvera_e_dispatch_sender"],
    "data": [
        "data/ubl_tr_templates.xml",
        "views/account_move_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,

}