# User Stories

Translated from [`SOLUTION_DESIGN.md`](SOLUTION_DESIGN.md) into stories a
development team could actually pick up and build from — this is the kind
of translation step a Junior Integration Architect does between the
technical design and the engineering backlog.

---

### US-1 — View product availability on the storefront

**As a** storefront frontend developer
**I want** a single REST endpoint that returns a product's stock and
current price
**So that** I don't have to integrate with the legacy warehouse SOAP
service or the pricing service myself

**Acceptance criteria:**
- **Given** a valid SKU that exists in the warehouse system
  **When** I call `GET /products/{sku}/availability`
  **Then** I receive `200 OK` with `sku`, `product_name`, `in_stock`,
  `quantity_available`, `base_price`, `final_price`, `currency`
- **Given** a SKU with an active promotion
  **When** I call the endpoint
  **Then** `final_price` reflects the discount, and `discount_percent` /
  `promo_active` are included in the response

*Implements:* `app/experience_api/routes.py`
*Verified by:* `tests/test_experience_api.py::test_availability_merges_stock_and_active_promotion`

---

### US-2 — Clear error when a product doesn't exist

**As a** storefront frontend developer
**I want** a proper `404` for an unknown SKU
**So that** I can show a "product not found" page instead of a confusing
generic error

**Acceptance criteria:**
- **Given** a SKU with no record in the warehouse system
  **When** I call `GET /products/{sku}/availability`
  **Then** I receive `404 Not Found` with a human-readable `detail` message

*Implements:* `app/process_api/inventory_service.py` (raises `ProductNotFoundError`), `app/experience_api/routes.py` (maps it to `404`)
*Verified by:* `tests/test_experience_api.py::test_availability_404s_for_unknown_sku`

---

### US-3 — Product page still works if the promotions service is down

**As a** storefront user
**I want** to still see a product's stock and full price even if the
promotions system is temporarily unavailable
**So that** an unrelated outage doesn't stop me from seeing or buying the product

**Acceptance criteria:**
- **Given** the pricing system is unreachable
  **When** I call `GET /products/{sku}/availability` for a SKU that exists
  **Then** I still receive `200 OK`, with `promo_active: false` and
  `final_price` equal to `base_price`

*Implements:* `app/process_api/inventory_service.py` (graceful fallback — see Solution Design §4)
*Verified by:* `tests/test_experience_api.py::test_availability_still_succeeds_when_pricing_is_down`

---

### US-4 — Honest error when the warehouse itself is down

**As a** storefront operations engineer
**I want** a clear `502` when the warehouse system can't be reached
**So that** I can distinguish "this product doesn't exist" from
"our systems are having a problem" in monitoring/alerting

**Acceptance criteria:**
- **Given** the warehouse system is unreachable or times out
  **When** I call `GET /products/{sku}/availability`
  **Then** I receive `502 Bad Gateway` naming which upstream system failed

*Implements:* `app/system_api/warehouse_client.py` (raises `UpstreamSystemError`), `app/experience_api/routes.py` (maps it to `502`)
*Verified by:* `tests/test_experience_api.py::test_availability_502s_when_warehouse_is_down`

---

### US-5 (future) — Add a loyalty-tier pricing source

**As a** product owner
**I want** logged-in customers with a loyalty tier to see their tier's price
**So that** we can reward repeat customers directly on the product page

**Acceptance criteria (draft — not yet implemented):**
- **Given** a customer with an active loyalty tier
  **When** they call `GET /products/{sku}/availability?customerId=...`
  **Then** the response includes a `loyalty_price` field reflecting their tier's discount

*Notes for the team:* per Solution Design §7, this only requires a new
System API (`system_api/loyalty_client.py`) and a new mapping/merge step
— the Experience API's existing consumers are unaffected. Flagged here as
a realistic example of how new integration requirements get scoped and
hooked into this architecture without a rewrite.
