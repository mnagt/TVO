# Copyright 2008-2016 Camptocamp
# Copyright 2019 Brainbean Apps (https://brainbeanapps.com)
# Copyright 2020 CorporateHub (https://corporatehub.eu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Currency Rate Update - TCMB",
    "version": "18.0.1.0.1",
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
