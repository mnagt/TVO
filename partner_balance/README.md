# Partner Balance Statement Add-on
[![Odoo Version](https://img.shields.io/badge/Odoo-15.0-purple.svg)](https://www.odoo.com/)
[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)


## Problem

Odoo's default partner ledger reports fail to properly handle:

1. **Multi-currency transactions** - No clear separation of balances by currency
2. **Opening balances** - Incorrect cumulative calculations when filtering by date ranges
3. **Partner-specific currencies** - Cannot view statements in the partner's pricelist currency
4. **Grouped reports** - Opening balances not calculated per currency group
5. **Excel exports** - Missing professional formatting and proper totals with opening balances

## Solution

This add-on provides three specialized partner balance reports:

### 1. Statement of Account (Default)
- Displays all transactions in company currency (TRY)
- Shows proper opening balance before date filter
- Cumulative balance calculation with mixed currencies

### 2. Statement Currency-based
- Groups transactions by currency
- Separate opening balance per currency
- Clean view of each currency's activity

### 3. Statement in Partner Currency  
- Converts all transactions to partner's pricelist currency
- Enables partners to view statements in their working currency
- Automatic currency conversion based on transaction dates

### Key Features

- **Dynamic opening balances** - Recalculated when date filters change
- **Journal filtering** - Excludes specific journals (KRFRK) from calculations
- **Excel export** - Professional formatting with headers, summaries, and totals
- **Real-time updates** - JavaScript-based date filtering with instant balance updates
- **Type classification** - Identifies transaction types (Invoice, Payment, Check, etc.)

### Technical Highlights

- SQL view-based reporting for performance
- Computed fields for cumulative balances
- Context-aware opening balance calculations
- Grouped and ungrouped data handling in Excel exports
- Currency conversion using Odoo's rate tables

---

**Access:** Partner form → "SOA" button