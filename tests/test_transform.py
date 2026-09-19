"""Unit tests for the mapping/transformation layer — pure functions, no
network, no app, no database. These should be the fastest and simplest
tests in the whole suite, and the ones you'd reach for first when a
mapping rule needs to change."""
from app.system_api.pricing_client import PricingRaw
from app.system_api.warehouse_client import WarehouseStockRaw
from app.transform.mappings import map_pricing, map_warehouse_stock, merge_product_availability


def test_map_warehouse_stock_converts_cents_to_euros():
    raw = WarehouseStockRaw(
        sku="WM-1001", article_name="Iron Diver", qty_on_hand=12,
        unit_price_cents=499900, currency="EUR", warehouse_location="HH-01",
    )
    result = map_warehouse_stock(raw)
    assert result["base_price"] == 4999.00
    assert result["product_name"] == "Iron Diver"


def test_map_warehouse_stock_zero_quantity_means_out_of_stock():
    raw = WarehouseStockRaw(
        sku="WM-2002", article_name="Pearl Necklace", qty_on_hand=0,
        unit_price_cents=189000, currency="EUR", warehouse_location="HH-01",
    )
    result = map_warehouse_stock(raw)
    assert result["in_stock"] is False
    assert result["quantity_available"] == 0


def test_map_pricing_passes_through_fields():
    raw = PricingRaw(sku="WM-1001", discount_percent=10, promo_active=True)
    assert map_pricing(raw) == {"discount_percent": 10, "promo_active": True}


def test_merge_applies_discount_when_promo_active():
    stock = {
        "sku": "WM-1001", "product_name": "Iron Diver", "in_stock": True,
        "quantity_available": 12, "currency": "EUR", "base_price": 100.00,
        "warehouse_location": "HH-01",
    }
    pricing = {"discount_percent": 10, "promo_active": True}

    result = merge_product_availability(stock, pricing)
    assert result["final_price"] == 90.00
    assert result["discount_percent"] == 10


def test_merge_ignores_discount_when_promo_inactive():
    stock = {
        "sku": "WM-1001", "product_name": "Iron Diver", "in_stock": True,
        "quantity_available": 12, "currency": "EUR", "base_price": 100.00,
        "warehouse_location": "HH-01",
    }
    pricing = {"discount_percent": 10, "promo_active": False}

    result = merge_product_availability(stock, pricing)
    assert result["final_price"] == 100.00


def test_merge_falls_back_gracefully_when_pricing_is_unavailable():
    stock = {
        "sku": "WM-1001", "product_name": "Iron Diver", "in_stock": True,
        "quantity_available": 12, "currency": "EUR", "base_price": 100.00,
        "warehouse_location": "HH-01",
    }

    result = merge_product_availability(stock, pricing=None)
    assert result["final_price"] == 100.00
    assert result["discount_percent"] == 0
    assert result["promo_active"] is False
