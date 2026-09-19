# Solution Design — Product Availability Integration

**Status:** Implemented · **Author:** Integration Hub team · **Pattern:** API-led connectivity

## 1. Business problem

The storefront frontend needs to answer one question for a product page:
*"Is this in stock, and what does it cost right now?"*

That answer depends on two systems that were never built to know about
each other:

| System | Owns | Protocol | Notes |
|---|---|---|---|
| Warehouse System | stock quantity, catalog price, warehouse location | SOAP-style XML over HTTP | Legacy — the business depends on it, too costly/risky to replace |
| Pricing & Promotions System | active discounts | REST/JSON | Newer, independently deployed |

The storefront should not have to know either system exists, what
protocol they speak, or how to combine their answers. That's what this
integration layer is for.

## 2. Architecture: API-led connectivity

This follows the same three-layer pattern MuleSoft's Anypoint Platform is
built around (System API / Process API / Experience API), implemented
here with plain FastAPI + httpx rather than Anypoint Studio/Mule
runtime — the pattern is the point, not the specific tooling:

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  Storefront │────▶│   Experience API │────▶│    Process API   │────▶│    System APIs    │
│  (consumer) │     │  GET /products/   │     │  orchestration,  │     │  warehouse_client │───▶ Warehouse System (SOAP/XML)
│             │     │  {sku}/availability│     │  merge, rules    │     │  pricing_client   │───▶ Pricing System (REST/JSON)
└─────────────┘     └──────────────────┘     └─────────────────┘     └──────────────────┘
```

**Why three layers instead of one script that does everything:**

- **System API** (`app/system_api/`) — one per backend, a thin and
  *faithful* wrapper that speaks that backend's native protocol and
  vocabulary unchanged. If the warehouse system is ever replaced with a
  different one, only `warehouse_client.py` changes — nothing above it does.
- **Process API** (`app/process_api/`) — where business rules and
  cross-system orchestration live. This is the *only* layer allowed to
  know that "availability" requires calling two systems and merging them.
- **Experience API** (`app/experience_api/`) — the contract the
  storefront actually depends on. Deliberately thin: HTTP concerns only,
  no business logic. A second consumer (e.g. a mobile app wanting a
  different response shape) would get its *own* Experience API reusing
  the same Process API underneath, rather than duplicating logic.

## 3. Data transformation

Raw backend data is never handed to a consumer unchanged — each source is
mapped into a clean, canonical shape first. Full field-by-field rules are
in [`MAPPING_SPECIFICATION.md`](MAPPING_SPECIFICATION.md); implemented in
`app/transform/mappings.py`.

## 4. Resilience & partial degradation

Not every upstream system is equally critical, and the design treats them
differently on purpose:

| System | If it's down or 404s | Why |
|---|---|---|
| Warehouse | Whole request fails (`404` if not found, `502` if unreachable) | It's the *only* source of truth for "does this product exist / is it in stock." Returning a fabricated answer would be worse than an honest error. |
| Pricing | Request still succeeds, with `promo_active: false`, no discount applied | "We don't currently know about a promotion" is a safe, honest default. Failing the entire product page because a secondary discount service hiccupped would hurt the business far more than briefly showing full price. |

This is a deliberate trade-off, not a missing error handler — see
`app/process_api/inventory_service.py` for where it's implemented, and
`tests/test_experience_api.py::test_availability_still_succeeds_when_pricing_is_down`
for where it's proven.

Both backend calls also run **concurrently** (`asyncio.gather`), not
sequentially — there's no dependency between them, so there's no reason
to make the caller wait twice as long.

## 5. Sequence: a successful request

```
Storefront          Experience API        Process API         Warehouse System   Pricing System
    │  GET /products/WM-1001/availability  │                        │                  │
    │───────────────────────▶│              │                        │                  │
    │                        │  get_product_availability("WM-1001")  │                  │
    │                        │─────────────▶│                        │                  │
    │                        │              │  fetch_stock (POST XML)│                  │
    │                        │              │───────────────────────▶│                  │
    │                        │              │  fetch_pricing (GET)   │                  │
    │                        │              │────────────────────────────────────────▶ │
    │                        │              │◀─────── StockResponse ─│                  │
    │                        │              │◀──────────────── {discount, promo} ───────│
    │                        │              │  map + merge           │                  │
    │                        │◀─────────────│                        │                  │
    │◀───────────────────────│  200 JSON     │                        │                  │
```

## 6. Error taxonomy

| Scenario | HTTP status | Body |
|---|---|---|
| Product doesn't exist (warehouse says so) | `404` | `{"detail": "No such product: '...'"}` |
| Warehouse unreachable / times out / bad response | `502` | `{"detail": "Upstream system 'warehouse' is currently unavailable..."}` |
| Pricing unreachable / 404 | *(none — see §4)* | Full `200` response, `promo_active: false` |

## 7. How this would extend

Adding a third backend (say, a CRM system providing loyalty-tier pricing)
would mean: one new `system_api/crm_client.py`, one new mapping function
in `transform/`, and updating `process_api/inventory_service.py`'s
orchestration to also call and merge it — the Experience API and its
consumers wouldn't need to change at all. This is the core payoff of
API-led connectivity: growth happens by *adding* System APIs, not by
rewriting the layers above them.
