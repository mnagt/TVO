# Copyright 2024 Coflow Team
# License LGPLv3 or later (https://www.gnu.org/licenses/lgpl-3.0).

{
    'name': 'Coflow Vomsis Entegrasyonu',
    'summary': """Vomsis online banka ekstre entegrasyonları""",
    'description': """Vomsis online banka ekstre entegrasyonları""",
    'version': '18.0.1.0.1',
    'license': 'LGPL-3',
    "category": "Accounting",
    'author': 'Coflow Team',
    'website': 'https://coflow.com.tr',
    'depends': ['account_statement_import_online'],
    'data': [
        'views/provider_vomsis.xml',
        'views/account_journal_dashboard_view.xml',
        'views/account_bank_statement_views.xml',
    ],
    'demo': [
    ],
}
