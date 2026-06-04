version: Odoo version is 18.0
path: Odoo basecode path: /var/odoo/stagetvo/src/addons
company currency: USD
***********************
Module: logistics
***********************
The problem: coding the algorithm.
***********************
The goal: Detect how many methods needed, what are they, where to implement.
***********************

***********************
Make your analysis and review to setup a solid plan for.


Analysis: Missing Paths & Issues

  1. Quantity exceeds remaining (unhandled)

  The algorithm handles qty < required → accept but never addresses qty > remaining. If a user enters more than what's left unshipped, there's no check. Proposed: warn but allow (partial over-allocation is sometimes intentional for re-exports).

  2. "Populate remaining" formula is undefined

  For the 2nd+ container, "remaining" needs a precise definition:

  ▎ remaining_qty = requisition_line.product_qty − Σ(container_line.product_qty for all OTHER containers on this requisition)

  If remaining is 0 for a product, that line should be skipped (not pre-populated with 0).

  3. What happens AFTER the confirm message?

  "Confirm message" appears twice but neither specifies the outcome on cancel. Proposed:
  - On cancel → revert the offending change (remove the unknown product or restore qty)
  - On confirm → keep as-is and allow save

  4. Requisition changed on an existing DRAFT container (unhandled)

  The algorithm enters the "draft → continue to requisition block" but doesn't say what to do with existing lines that belong to the old requisition. Proposed: warn the user that existing lines will NOT be re-populated automatically, and offer to
  clear + re-populate.

  5. New container, requisition has zero lines

  If the requisition has no lines yet (it's still being negotiated), "populate all requisition lines" would produce nothing. Proposed: allow silently, leave container lines empty.

  6. Locked states — editing existing lines

  The algorithm says "lock all fields and lock adding new lines" for non-draft containers. Does this also lock editing existing lines (e.g. updating wh_arriving_date, customs_declaration_id)? Proposed: lock structural fields (product, qty) but keep
   operational fields (dates, customs, transit) editable on shipped+ containers.

  7. No cancellation path

  There is no cancelled container state. If a container is abandoned mid-process, the "remaining" calculation for subsequent containers will be wrong. Proposed: add this to a future state machine discussion — not blocking now.

  ---
  Revised Algorithm Diagram

  START: Container form action
  │
  ├─ [NEW record]
  │   │
  │   ├─ requisition_id SET?
  │   │   │
  │   │   ├─ NO → allow, no lines pre-populated
  │   │   │
  │   │   └─ YES
  │   │       │
  │   │       ├─ requisition has lines?
  │   │       │   └─ NO → allow, leave lines empty
  │   │       │
  │   │       └─ YES
  │   │           │
  │   │           ├─ is this the FIRST container on this requisition?
  │   │           │   │
  │   │           │   ├─ YES → pre-populate ALL requisition lines
  │   │           │   │         (product_id, product_qty copied from each line)
  │   │           │   │
  │   │           │   └─ NO  → pre-populate REMAINING lines only
  │   │           │             (skip products where remaining_qty = 0)
  │   │           │             remaining_qty = req_line.qty
  │   │           │                           − Σ other containers' lines for same product
  │   │           │
  │   │           └─ [User edits lines]
  │   │               │
  │   │               ├─ Product NOT in requisition added?
  │   │               │   └─ Confirm: "This product is not in the deal. Keep it?"
  │   │               │       ├─ YES → keep line
  │   │               │       └─ NO  → remove line
  │   │               │
  │   │               ├─ Quantity < pre-populated qty?
  │   │               │   └─ Accept silently (partial shipment is valid)
  │   │               │
  │   │               ├─ Quantity > remaining_qty?
  │   │               │   └─ Warn: "Quantity exceeds remaining on deal." Allow save.
  │   │               │
  │   │               └─ [SAVE]
  │   │                   └─ If any unconfirmed changes → show confirmation summary
  │
  └─ [EXISTING record]
      │
      ├─ state = DRAFT?
      │   │
      │   ├─ YES
      │   │   │
      │   │   ├─ requisition_id CHANGED?
      │   │   │   └─ Warn: "Existing lines belong to the old deal.
      │   │   │           Clear and re-populate from new deal?"
      │   │   │       ├─ YES → clear lines, re-populate (same logic as NEW)
      │   │   │       └─ NO  → keep existing lines, flag mismatch
      │   │   │
      │   │   └─ requisition_id UNCHANGED → continue editing (same rules as NEW)
      │   │
      │   └─ NO (shipped / in_transit / arrived / antrepo / released / unloaded)
      │       │
      │       ├─ Lock: product_id, product_qty, container_number, requisition_id,
      │       │         bill_lading_id, adding/removing container lines
      │       │
      │       └─ Keep editable: wh_arriving_date, customs_declaration_id,
      │                          transit_trip_id, antrepo_arrival_date,
      │                          customer_* fields, activity_status