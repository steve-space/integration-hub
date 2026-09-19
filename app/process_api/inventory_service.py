"""
Process API layer: orchestration and business rules.

This is where multiple System APIs get called and combined into one
answer. It's the layer that knows the *business* rule "a product's
availability is its warehouse stock, priced according to any active
promotion" — a rule that doesn't belong in either System API (which each
only know about their own single backend) and doesn't belong in the
Experience API (which should stay a thin, protocol-facing layer).
"""
import asyncio

import httpx

from app.exceptions import ProductNotFoundError, UpstreamNotFoundError, UpstreamSystemError
from app.system_api.pricing_client import fetch_pricing
from app.system_api.warehouse_client import fetch_stock
from app.transform.mappings import map_pricing, map_warehouse_stock, merge_product_availability


async def get_product_availability(sku: str, client: httpx.AsyncClient) -> dict:
    """Look up one product's combined stock + pricing information.

    The two backend calls run concurrently (asyncio.gather), since they're
    independent of each other — no reason to wait for the warehouse
    response before starting the pricing request.

    Design decision (see docs/SOLUTION_DESIGN.md for the full rationale):
      - The warehouse system is AUTHORITATIVE for "does this product
        exist at all?". If it says not found, or is down, this function
        fails loudly.
      - The pricing system is NOT authoritative — if it's down or has no
        promotion configured, we still return a valid answer (just with
        no discount applied), because "we don't know about any active
        promotion" is a reasonable, safe default, whereas silently
        hiding a real out-of-stock product would not be.
    """
    stock_result, pricing_result = await asyncio.gather(
        fetch_stock(sku, client),
        fetch_pricing(sku, client),
        return_exceptions=True,
    )

    if isinstance(stock_result, UpstreamNotFoundError):
        raise ProductNotFoundError(f"No such product: '{sku}'")
    if isinstance(stock_result, UpstreamSystemError):
        raise stock_result
    if isinstance(stock_result, BaseException):
        raise stock_result  # anything unexpected — never swallow silently

    stock = map_warehouse_stock(stock_result)

    pricing: dict | None
    if isinstance(pricing_result, (UpstreamNotFoundError, UpstreamSystemError)):
        # Non-critical system degraded — fall back gracefully rather than
        # failing the whole request. In production this branch would also
        # emit a metric/log line so the degradation is visible to ops,
        # even though the caller still gets a successful response.
        pricing = None
    elif isinstance(pricing_result, BaseException):
        raise pricing_result
    else:
        pricing = map_pricing(pricing_result)

    return merge_product_availability(stock, pricing)
