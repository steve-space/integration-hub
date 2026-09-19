"""End-to-end tests of the Experience API, with both backend systems
mocked via `respx`. These prove the full chain works together: HTTP
request -> System API calls -> transform -> merge -> HTTP response —
including the two resilience behaviors that matter most for an
integration layer: a hard failure when the authoritative system (the
warehouse) is unreachable, and a graceful fallback when the non-critical
system (pricing) is."""
import httpx
import respx
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

WAREHOUSE_URL = f"{settings.warehouse_system_url}/WarehouseService"
PRICING_URL = f"{settings.pricing_system_url}/pricing/WM-1001"

STOCK_XML_OK = (
    "<StockResponse><Sku>WM-1001</Sku><ArticleName>Iron Diver</ArticleName>"
    "<QtyOnHand>12</QtyOnHand><UnitPriceCents>10000</UnitPriceCents>"
    "<Currency>EUR</Currency><WarehouseLocation>HH-01</WarehouseLocation></StockResponse>"
)
STOCK_XML_NOT_FOUND = "<Fault><Code>SKU_NOT_FOUND</Code><Message>No such SKU</Message></Fault>"


@respx.mock
def test_availability_merges_stock_and_active_promotion():
    respx.post(WAREHOUSE_URL).mock(return_value=httpx.Response(200, text=STOCK_XML_OK))
    respx.get(PRICING_URL).mock(
        return_value=httpx.Response(200, json={"sku": "WM-1001", "discount_percent": 10, "promo_active": True})
    )

    with TestClient(app) as client:
        response = client.get("/products/WM-1001/availability")

    assert response.status_code == 200
    body = response.json()
    assert body["in_stock"] is True
    assert body["base_price"] == 100.0
    assert body["final_price"] == 90.0


@respx.mock
def test_availability_404s_for_unknown_sku():
    respx.post(WAREHOUSE_URL).mock(return_value=httpx.Response(500, text=STOCK_XML_NOT_FOUND))
    respx.get(PRICING_URL).mock(return_value=httpx.Response(404, json={"detail": "not found"}))

    with TestClient(app) as client:
        response = client.get("/products/WM-1001/availability")

    assert response.status_code == 404


@respx.mock
def test_availability_502s_when_warehouse_is_down():
    respx.post(WAREHOUSE_URL).mock(side_effect=httpx.ConnectError("connection refused"))
    respx.get(PRICING_URL).mock(
        return_value=httpx.Response(200, json={"sku": "WM-1001", "discount_percent": 10, "promo_active": True})
    )

    with TestClient(app) as client:
        response = client.get("/products/WM-1001/availability")

    assert response.status_code == 502


@respx.mock
def test_availability_still_succeeds_when_pricing_is_down():
    """The core resilience behavior this project is built to demonstrate:
    a non-critical system being down degrades the response gracefully
    instead of failing the whole request."""
    respx.post(WAREHOUSE_URL).mock(return_value=httpx.Response(200, text=STOCK_XML_OK))
    respx.get(PRICING_URL).mock(side_effect=httpx.ConnectError("connection refused"))

    with TestClient(app) as client:
        response = client.get("/products/WM-1001/availability")

    assert response.status_code == 200
    body = response.json()
    assert body["promo_active"] is False
    assert body["final_price"] == body["base_price"]
