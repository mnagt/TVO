# Copyright 2026 Yaser Akhras
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    'name': 'MIS Builder Extensions',
    'version': '18.0.1.0.0',
    'category': 'Reporting',
    'summary': 'Extended functionality and enhancements for MIS Builder',
    'description': """
        MIS Builder Extensions

        This module provides various extensions and enhancements for MIS Builder.
        It includes improved methods, additional models, and enhanced reporting capabilities.
        
        Features:
        - Enhanced _get_account_name method for better account name resolution
        - Extended KPI Matrix model with additional functionalities
        - Improved account mapping and categorization
        - Better performance for large datasets
        - Extensible framework for future MIS Builder developments
    """,
    'author': 'Yaser Akhras',
    'website': 'https://www.yaserakhras.com',
    'license': 'LGPL-3',
    'depends': [
        'mis_builder',
    ],
    'data': [ ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'development_status': 'Alpha',
    'maintainers': ['yaserakhras'],
}