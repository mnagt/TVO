# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'HR Expense Extension',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Expenses',
    'summary': 'Adds total amount in currency to expense sheets',
    'description': """
HR Expense Extension

Extends expense sheets with a computed total of expense line amounts
in their original currency.
    """,
    'author': 'Yaser Akhras',
    'website': 'https://www.yaserakhras.com',
    'license': 'LGPL-3',
    'depends': [
        'hr_expense',
    ],
    'data': [
        'views/hr_expense_views.xml',
        'report/hr_expense_report.xml',
    ],
    'installable': True,
}
