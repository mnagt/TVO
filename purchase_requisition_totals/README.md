# Purchase Requisition Tax Management
[![Odoo Version](https://img.shields.io/badge/Odoo-15.0-purple.svg)](https://www.odoo.com/)
[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)

## Problem
Standard Odoo purchase requisitions lack tax calculation capabilities, causing:
- **Inaccurate cost estimation** - Cannot see total cost including taxes during planning phase
- **Budget discrepancies** - Requisition amounts differ from actual purchase order totals
- **Manual calculations** - Users must calculate taxes separately for accurate budgeting
- **Poor decision making** - Approvers lack complete financial picture when reviewing requisitions

## Solution
This module extends purchase requisitions with comprehensive tax management:
- **Line-level tax selection** - Apply multiple taxes to each requisition line
- **Automatic calculations** - Real-time computation of subtotals, taxes, and totals
- **Visual tax breakdown** - Account-style tax totals widget for clear presentation
- **Accurate forecasting** - See exact costs before creating purchase orders
- **Multi-currency support** - Proper rounding and currency handling

## Benefits
- Accurate budget planning and approval process
- Eliminates discrepancies between requisitions and purchase orders
- Faster approvals with complete cost visibility
- Better vendor comparison with tax-inclusive pricing

## Technical Details

### Models Extended
- `purchase.requisition` - Adds tax total fields and computation methods
- `purchase.requisition.line` - Adds tax field and amount calculations

### Key Fields Added
**Header Level:**
- `amount_untaxed` - Subtotal before taxes
- `amount_tax` - Total tax amount
- `amount_total` - Grand total
- `tax_totals_json` - Tax breakdown for widget display

**Line Level:**
- `taxes_id` - Many2many relation to account.tax
- `price_subtotal` - Line amount before tax
- `price_tax` - Tax amount for line
- `price_total` - Line total with tax


## Usage
1. Create/edit a purchase requisition
2. Select taxes on each line (supports multiple taxes)
3. View automatic calculation of totals
4. Review tax breakdown at form bottom
