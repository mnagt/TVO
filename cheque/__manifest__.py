# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Cheque Management',
    'version': "18.0.1.0.3",
    'category': 'Accounting',
    'summary': 'Cheques Management',
    'description': """
      Checks Management

    This module allows you to manage the cheques received from your customers or issued to your suppliers.
    You can track the status of each cheque (issued, received, deposited, cached, bounced) and generate reports on cheque transactions.
    """,
    'author': 'Yaser Akhras',
    'website': 'https://www.yaserakhras.com',
    'license': 'LGPL-3',
    'depends': [
        'account',
    ],
    'data': [
        'data/account_payment_method_data.xml',
        'data/cheque_state_option_data.xml',
        'security/ir.model.access.csv',
        'security/security.xml',
        'wizards/cheque_wizard.xml',
        'wizards/cheque_bulk_state_update_view.xml',
        'wizards/cheque_deposit_wizard.xml',
        'views/account_payment_view.xml',
        'views/account_journal_view.xml',
        'views/cheque_view.xml',
        'wizards/account_payment_register_views.xml',
    ],
    'installable': True,
}
