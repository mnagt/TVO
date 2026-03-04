{
    'name': 'Sale Extension - SO to PO',
    'version': '18.0.1.0.0',
    'summary': 'Convert Sale Orders to Purchase Orders for intercompany transactions',
    'description': """
        This module allows users to convert confirmed sale orders into purchase orders
        for intercompany transactions. When a sale order is created with a customer
        that is also an Odoo company, users can generate a matching purchase order
        in the customer's company with the seller as the vendor.
    """,
    'category': 'Sales/Purchase',
    'author': 'Yaser Akhras',
    'website': 'https://www.yaserakhras.com',
    'license': 'LGPL-3',
    'depends': [
        'sale_extension',
        'purchase',
    ],
    'data': [
        'data/data.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
        'wizards/so_to_po_wizard.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}