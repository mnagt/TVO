# -*- coding: utf-8 -*-

{
    "name": "Currency Rate Update - TCMB",
    "version": "18.0.1.1.0",
    "author": "Camptocamp, CorporateHub, Odoo Community Association (OCA)",
    "maintainers": "Yaser Akhras",
    "website": "https://yaserakhras.com",
    "license": "AGPL-3",
    "category": "Financial Management/Configuration",
    "summary": "Update exchange rates from Central Bank of the Republic of Türkiye (TCMB) based on OCA modules: https://github.com/OCA/currency",
    "depends": ["base", "mail", "account"],
    "data": [
        "data/cron.xml",
        "security/ir.model.access.csv",
        "security/res_currency_rate_provider.xml",
        "wizards/res_tcmb_wizard.xml",
        "views/res_currency_rate.xml",
        "views/res_currency_rate_provider.xml",
        "views/res_config_settings.xml",
    ],
    "installable": True,
}
