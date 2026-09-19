# Mapping Specification

This document is the field-by-field transformation contract for this
integration — the same role a DataWeave script's documentation plays in a
MuleSoft project. Every rule listed here is implemented in
`app/transform/mappings.py` and covered by a test in `tests/test_transform.py`.

## 1. Warehouse System → Canonical Stock

Source: `StockResponse` XML from the legacy warehouse system (via
`app/system_api/warehouse_client.py`).

| Source field (XML) | Type | Target field | Type | Rule |
|---|---|---|---|---|
| `Sku` | string | `sku` | string | Direct copy |
| `ArticleName` | string | `product_name` | string | Renamed — "Article" is the warehouse's internal term; the storefront/API consumers use "product" |
| `QtyOnHand` | integer | `quantity_available` | integer | Direct copy |
| `QtyOnHand` | integer | `in_stock` | boolean | Derived: `true` if `QtyOnHand > 0`, else `false` |
| `UnitPriceCents` | integer | `base_price` | decimal | Converted: `UnitPriceCents / 100`, rounded to 2 decimal places. The warehouse stores money as integer cents to avoid floating-point rounding issues internally; API consumers expect a normal decimal euro amount. |
| `Currency` | string | `currency` | string | Direct copy |
| `WarehouseLocation` | string | `warehouse_location` | string | Direct copy |

## 2. Pricing System → Canonical Pricing

Source: JSON from the pricing system (via `app/system_api/pricing_client.py`).

| Source field (JSON) | Type | Target field | Type | Rule |
|---|---|---|---|---|
| `discount_percent` | integer (0–100) | `discount_percent` | integer | Direct copy |
| `promo_active` | boolean | `promo_active` | boolean | Direct copy |

*(Field names already match here — the mapping function still exists as
its own explicit step rather than being skipped, so a future field rename
in the pricing system only requires a one-line change in one place.)*

## 3. Merge → Final Experience API Response

Combines the two canonical fragments above (`app/transform/mappings.py::merge_product_availability`):

| Target field | Rule |
|---|---|
| `sku`, `product_name`, `in_stock`, `quantity_available`, `currency`, `base_price`, `warehouse_location` | Copied from canonical stock, unchanged |
| `discount_percent` | From canonical pricing; `0` if pricing was unavailable (see Solution Design §4) |
| `promo_active` | From canonical pricing; `false` if pricing was unavailable |
| `final_price` | If `promo_active` is `true` and `discount_percent > 0`: `round(base_price * (1 - discount_percent / 100), 2)`. Otherwise: equal to `base_price`. |

### Worked example

Input — warehouse: `UnitPriceCents=499900`; pricing: `discount_percent=10, promo_active=true`

```
base_price   = 499900 / 100        = 4999.00
final_price  = 4999.00 * (1 - 0.10) = 4499.10
```

Matches the live example in `README.md` and the assertions in
`tests/test_transform.py::test_merge_applies_discount_when_promo_active`.
