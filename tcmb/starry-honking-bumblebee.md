# TCMB Currency Rate Module - Complete Rate Implementation Plan

## Objective
Add support for all 4 TCMB rate types per currency (currently only 2 are captured).

## Current vs Target State

| Rate Type | Turkish Name | Current | Target |
|-----------|--------------|---------|--------|
| ForexBuying | Döviz Alış | ✅ `rate` field | ✅ Keep as-is |
| ForexSelling | Döviz Satış | ❌ Missing | ✅ New `forex_selling_rate` |
| BanknoteBuying | Efektif Alış | ❌ Missing | ✅ New `banknote_buying_rate` |
| BanknoteSelling | Efektif Satış | ✅ `banknote_selling_rate` | ✅ Keep as-is |

---

## Implementation Tasks

### Task 1: Add New Fields to res.currency.rate Model
**File:** `models/res_currency_rate.py`

Add two new fields:
```python
forex_selling_rate = fields.Float(
    string="Forex Selling Rate",
    digits=(12, 6),
    tracking=True,
    help="TCMB Döviz Satış (Forex Selling) rate",
)
banknote_buying_rate = fields.Float(
    string="Banknote Buying Rate",
    digits=(12, 6),
    tracking=True,
    help="TCMB Efektif Alış (Banknote Buying) rate",
)
```

Update the `write` method to include new fields in the provider unlinking logic.

---

### Task 2: Update XML Handler to Capture All 4 Rates
**File:** `models/res_currency_rate_provider_tcmb.py`

Modify `TcmbRatesHandler` class:
1. Add new storage dictionaries: `forex_selling`, `banknote_buying`
2. Update `endElement` to capture `ForexSelling` and `BanknoteBuying` elements

```python
# In __init__:
self.forex_selling = defaultdict(dict)
self.banknote_buying = defaultdict(dict)

# In endElement:
elif name == "ForexSelling":
    self.forex_selling[self.date.isoformat()][self.currency_code] = self.current_text.strip()
elif name == "BanknoteBuying":
    self.banknote_buying[self.date.isoformat()][self.currency_code] = self.current_text.strip()
```

---

### Task 3: Update _obtain_rates Return Value
**File:** `models/res_currency_rate_provider_tcmb.py`

Modify `_obtain_rates` method to return all 4 rate types:

```python
return {
    'forex_buying': content,           # existing (main rate)
    'forex_selling': forex_selling,    # new
    'banknote_buying': banknote_buying,# new
    'banknote_selling': banknote_selling,  # existing
}
```

Apply inversion calculation to all 4 rate dictionaries when base_currency != "TRY".

---

### Task 4: Update _update Method to Handle All 4 Rates
**File:** `models/res_currency_rate_provider.py`

Modify the `_update` method to:
1. Parse the new dict-based return format
2. Process all 4 rate types
3. Write all 4 rates to the currency rate record

```python
write_vals = {
    "rate": rate,  # forex_buying
    "forex_selling_rate": forex_selling_rate,
    "banknote_buying_rate": banknote_buying_rate,
    "banknote_selling_rate": banknote_selling_rate,
    "provider_id": provider.id,
}
```

---

### Task 5: Update Currency Rate Form View
**File:** `views/res_currency_rate.xml`

Add the new fields to the form view after the existing rate field:

```xml
<field name="rate" position="after">
    <field name="forex_selling_rate" />
    <field name="banknote_buying_rate" />
    <field name="banknote_selling_rate" />
    <field name="provider_id" readonly="1" />
</field>
```

---

### Task 6: Update Module Version
**File:** `__manifest__.py`

Bump version from `18.0.1.0.1` to `18.0.1.1.0` to reflect the new feature.

---

## Files to Modify Summary

| File | Changes |
|------|---------|
| `models/res_currency_rate.py` | Add 2 new fields, update write() |
| `models/res_currency_rate_provider_tcmb.py` | Update handler + _obtain_rates |
| `models/res_currency_rate_provider.py` | Update _update() method |
| `views/res_currency_rate.xml` | Add new fields to form view |
| `__manifest__.py` | Bump version |

---

## Verification

1. Install/upgrade the module
2. Configure TCMB provider with USD and EUR currencies
3. Run manual rate update via wizard
4. Verify all 4 rates are populated for each currency:
   - `rate` (ForexBuying)
   - `forex_selling_rate` (ForexSelling)
   - `banknote_buying_rate` (BanknoteBuying)
   - `banknote_selling_rate` (BanknoteSelling)
5. Check form view displays all 4 rate fields
6. Verify inversion works correctly when base currency is not TRY
