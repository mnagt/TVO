# -*- coding: utf-8 -*-
{
    'name': 'Advance Payment for Sale and Purchase',
    'version': '18.0.1.3.0',
    'summary': 'Register, track, and automatically reconcile advance down-payments directly from Sales Orders and Purchase Orders with distinct access rights controls.',
    'description': """
        Advance Payment for Sale and Purchase
        =====================================
        This module provides a powerful enterprise-grade financial utility designed for Odoo administrators, accounting clerks, purchasing agents, and sales management teams. It enables users to cleanly register advance down-payments directly from within source Sales Orders or Purchase Orders documents using a centralized interactive payment wizard, removing complex cross-module routing steps while enforcing security policies.

        The framework includes active accounting listeners that track down-payments across document types, calculation matrices to monitor outstanding residues, and context interceptors that automatically apply payments to future customer invoices or vendor bills upon validation.

        🚀 Key Functional Features:
        ---------------------------
        * **Direct Order-Level Advance Registration:** Adds a native action option to instantly deploy an advance payment register wizard without having to leave the source business document workflow.

        * **Centralized Financial Multi-Wizard:** Operates a intelligent transient utility (`advance.payment.wizard`) that dynamically adjusts processing parameters (Inbound/Outbound types, Customer/Vendor labels, Bank/Cash contexts) based on parent origin fields.

        * **Automated Residual Calculation Engine:** Computes immediate mathematical metrics (`total_amount`, `paid_amount`, `payment_difference`) to show live financial variables to operators before payment execution.

        * **Bidirectional Document Mapping:** Links generated `account.payment` structures back to source entities using high-performance Many2many relation layers (`advance_payment_ids`), preventing data isolation.

        * **Smart Access Rights Framework:** Deploys independent functional security groups (`Advance Payment (Sale)` and `Advance Payment (Purchase)`) enabling granular access configuration per corporate employee role.

        * **Deep Analytical Smart Buttons:** Extends core sales and procurement form interfaces with dynamic statistical dashboard counters tracking mapped payments and real-time ledger journal lines (`account.move.line`).

        * **Automatic Invoice Reconciliation Hook:** Inherits standard entry confirmation layers (`action_post`, `js_assign_outstanding_line`) to cleanly monitor outstanding records and ensure down-payments match future financial postings.

        🛡️ Advanced Processing & Integrity:
        ------------------------------------
        * Validates token parameters dynamically, forcing explicit user exceptions if entry amounts violate zero boundaries.
        * Intercepts standard low-level writing processes (`write`) to instantly trigger matrix reconciliations if payment flags or outstanding thresholds fluctuate.
        * Safely preserves payment records across draft deletions by locking core fields into system configuration logs.
        * Seamlessly switches tracking structures if alternative inbound payment method lines are updated on relevant banking books.

        ⚙️ Target Models & System Modifications:
        -----------------------------------------
        * `sale.order` (Form View Extended, Smart Counter Controls & Action Modifiers Added)
        * `purchase.order` (Procurement Layout Extended & Wizard Direct Call Anchored)
        * `account.move` (Post Routines Extended & Matching Hooks Overridden)
        * `res.users` (Access Rights Configuration Matrix Appended)
        * `advance.payment.wizard` (New Core Asynchronous Transient Controller Built)

        🔗 Business Benefits:
        ---------------------
        * **Optimizes Cash Flow Visibility:** Bridges the operational gap between frontline sales operations, procurement pipelines, and back-office accounting ledgers.
        * **Eliminates Processing Bottlenecks:** Eradicates hours of manual bookkeeping lookup tasks needed to trace down-payments against incoming invoices.
        * **Reduces Human Bookkeeping Errors:** Automated value mappings protect entries from data mismatch vulnerabilities during massive transactional cycles.
        * **Enforces Fiscal Internal Controls:** Restricts currency operations, banking selection routines, and financial entries strictly to authorized team roles.
    """,
    'author': 'SprintERP Technologies',
    'website': 'https://sprinterp.com',
    'category': 'Accounting',
    'license': 'LGPL-3',
    'depends': [
        'sale_management',
        'purchase',
        'account',
    ],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'wizard/advance_payment_wizard_view.xml',
        'views/sale_order_view.xml',
        'views/purchase_order_view.xml',
        'views/res_users_view.xml',
    ],
    'images': ['static/description/banner.gif'],
    'installable': True,
    'application': False,
    'price': 8.00,
    'currency': 'USD',
}
