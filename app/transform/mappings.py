"""
The data transformation / mapping layer — this project's equivalent of a
MuleSoft DataWeave script.

Every function here is a pure function: given the same input, it always
returns the same output, with no side effects (no network calls, no
database, no logging). That's deliberate — mapping/transformation logic
should be the easiest code in the whole system to read, test, and reason
about, since it's exactly the kind of code that quietly breaks a system
when it's wrong (e.g. a silent unit conversion bug).

Every mapping rule implemented here is also documented, field by field,
in docs/MAPPING_SPECIFICATION.md — the equivalent of the mapping
documentation a MuleSoft integration would produce for its DataWeave
transformations.
"""
from app.system_api.pricing_client import PricingRaw
from app.system_api.warehouse_client import WarehouseStockRaw


def map_warehouse_stock(raw: WarehouseStockRaw) -> dict:
    """Legacy warehouse fields -> canonical stock fields.

    Rules (see docs/MAPPING_SPECIFICATION.md for the full table):
      - qty_on_hand > 0            -> in_stock: true
      - unit_price_cents / 100     -> base_price (decimal euros, not cents)
      - article_name               -> product_name (renamed for clarity)
    """
    return {
        "sku": raw.sku,
        "product_name": raw.article_name,
        "quantity_available": raw.qty_on_hand,
        "in_stock": raw.qty_on_hand > 0,
        "base_price": round(raw.unit_price_cents / 100, 2),
        "currency": raw.currency,
        "warehouse_location": raw.warehouse_location,
    }


def map_pricing(raw: PricingRaw) -> dict:
    """Pricing system fields -> canonical pricing fields.

    This mapping is small (the source and target shapes are already close)
    but it still exists as its own explicit step rather than being skipped
    — so that if the pricing system's field names ever change, only this
    function needs updating, not every caller of it.
    """
    return {
        "discount_percent": raw.discount_percent,
        "promo_active": raw.promo_active,
    }


def merge_product_availability(stock: dict, pricing: dict | None) -> dict:
    """Combine the two canonical fragments into the final Experience API shape.

    `pricing` is Optional: if the pricing system is unavailable or has no
    promotion configured for this SKU, we deliberately do NOT fail the
    whole request — we fall back to "no discount" (see
    docs/SOLUTION_DESIGN.md, "Resilience & partial degradation" section,
    for why this is a considered choice and not just a missing error
    handler). The warehouse system, in contrast, IS authoritative and
    required — see process_api/inventory_service.py.
    """
    discount_percent = pricing["discount_percent"] if pricing else 0
    promo_active = pricing["promo_active"] if pricing else False

    final_price = stock["base_price"]
    if promo_active and discount_percent > 0:
        final_price = round(stock["base_price"] * (1 - discount_percent / 100), 2)

    return {
        "sku": stock["sku"],
        "product_name": stock["product_name"],
        "in_stock": stock["in_stock"],
        "quantity_available": stock["quantity_available"],
        "currency": stock["currency"],
        "base_price": stock["base_price"],
        "discount_percent": discount_percent,
        "promo_active": promo_active,
        "final_price": final_price,
        "warehouse_location": stock["warehouse_location"],
    }
