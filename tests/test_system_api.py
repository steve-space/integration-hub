"""Tests for the System API clients, with the actual backend HTTP calls
mocked out using `respx` — these tests never hit a real network, but they
do exercise the real XML-parsing and JSON-parsing code, plus the error
handling for "not found" vs. "system is down"."""
import httpx
import respx

from app.config import settings
from app.exceptions import UpstreamNotFoundError, UpstreamSystemError
from app.system_api.pricing_client import fetch_pricing
from app.system_api.warehouse_client import fetch_stock

WAREHOUSE_URL = f"{settings.warehouse_system_url}/WarehouseService"
PRICING_URL = f"{settings.pricing_system_url}/pricing/WM-1001"


@respx.mock
async def test_fetch_stock_parses_successful_response():
    respx.post(WAREHOUSE_URL).mock(
        return_value=httpx.Response(
            200,
            text=(
                "<StockResponse><Sku>WM-1001</Sku><ArticleName>Iron Diver</ArticleName>"
                "<QtyOnHand>12</QtyOnHand><UnitPriceCents>499900</UnitPriceCents>"
                "<Currency>EUR</Currency><WarehouseLocation>HH-01</WarehouseLocation></StockResponse>"
            ),
        )
    )
    async with httpx.AsyncClient() as client:
        result = await fetch_stock("WM-1001", client)

    assert result.sku == "WM-1001"
    assert result.qty_on_hand == 12
    assert result.unit_price_cents == 499900


@respx.mock
async def test_fetch_stock_raises_not_found_for_fault_response():
    respx.post(WAREHOUSE_URL).mock(
        return_value=httpx.Response(
            500,
            text="<Fault><Code>SKU_NOT_FOUND</Code><Message>No such SKU</Message></Fault>",
        )
    )
    async with httpx.AsyncClient() as client:
        try:
            await fetch_stock("UNKNOWN", client)
            assert False, "expected UpstreamNotFoundError"
        except UpstreamNotFoundError as exc:
            assert exc.system == "warehouse"


@respx.mock
async def test_fetch_stock_raises_system_error_when_unreachable():
    respx.post(WAREHOUSE_URL).mock(side_effect=httpx.ConnectError("connection refused"))
    async with httpx.AsyncClient() as client:
        try:
            await fetch_stock("WM-1001", client)
            assert False, "expected UpstreamSystemError"
        except UpstreamSystemError as exc:
            assert exc.system == "warehouse"


@respx.mock
async def test_fetch_pricing_parses_successful_response():
    respx.get(PRICING_URL).mock(
        return_value=httpx.Response(200, json={"sku": "WM-1001", "discount_percent": 10, "promo_active": True})
    )
    async with httpx.AsyncClient() as client:
        result = await fetch_pricing("WM-1001", client)

    assert result.discount_percent == 10
    assert result.promo_active is True


@respx.mock
async def test_fetch_pricing_raises_not_found_for_404():
    respx.get(PRICING_URL).mock(return_value=httpx.Response(404, json={"detail": "not found"}))
    async with httpx.AsyncClient() as client:
        try:
            await fetch_pricing("WM-1001", client)
            assert False, "expected UpstreamNotFoundError"
        except UpstreamNotFoundError as exc:
            assert exc.system == "pricing"
