{
    "name": "Post Dated Check Management",
    "author": "Nexera Innovations",
    "category": "Accounting",
    "license": "OPL-1",
    "summary": "Post-Dated Cheque Management, Manage Post-Dated Cheques App, View Vendor Invoice PDCs, List of Customer PDC Payments, Track Client PDC Processes, Register Vendor Post-Dated Cheques Module, Print Vendor PDC Reports, Print Customer PDC Reports in Odoo.",
    "description": """In invoicing and billing, a Post-Dated Cheque (PDC) refers to a cheque issued by a customer or vendor (payer) with a future date.
                   The ability to deposit or encash such cheques before their specified date differs from country to country. Since Odoo does not provide built-in functionality to manage post-dated cheques, this module has been developed to bridge that gap.
                   This module enables efficient management of post-dated cheques along with their corresponding accounting journal entries. It allows you to easily register, track, and manage post-dated cheques for both customers and vendors.
                   Cheques can be seamlessly moved through various stages — New, Registered, Returned, Deposited, Bounced, and Completed — with each stage automatically supported by the appropriate accounting journal entries.
                   Additionally, you can filter, view, and organize cheques based on their status and generate clear, easy-to-read PDF reports for record-keeping and analysis.""",
    'images': ['static/description/banner.jpg'],
    "depends": [
        "account"
    ],
    "data": [
        "data/ir_sequence.xml",
        "data/account_data.xml",
        "data/ir_cron_cust.xml",
        "data/ir_cron_ven.xml",
        "data/mail_templates.xml",
        "security/ir.model.access.csv",
        "security/pdc_security.xml",
        "security/report_payment_pdc.xml",
        "views/res_config_settings_views.xml",
        "wizard/pdc_payment_wizard_views.xml",
        "wizard/pdc_multi_action_views.xml",
        "wizard/partner_wizard_views.xml",
        "views/views.xml",
        "report/pdc_wizard.xml",
        "report/report_action.xml",
    ],


    "application": True,
    "auto_install": False,
    "installable": True,
    "price": 5.89,
    "currency": "USD",
}
