"""System API layer: the pricing & promotions system.

Same idea as warehouse_client.py, but for a modern REST/JSON backend
instead of a SOAP/XML one. A real Integration Architect connects to a mix
of old and new systems side by side — the System API layer is what lets
everything above it (transform, process, experience) stay ignorant of
which protocol any particular backend happens to speak.
"""
from dataclasses import dataclass

import httpx

from app.config import settings
from app.exceptions import UpstreamNotFoundError, UpstreamSystemError

SYSTEM_NAME = "pricing"


@dataclass
class PricingRaw:
    sku: str
    discount_percent: int
    promo_active: bool


async def fetch_pricing(sku: str, client: httpx.AsyncClient) -> PricingRaw:
    try:
        response = await client.get(
            f"{settings.pricing_system_url}/pricing/{sku}",
            timeout=settings.backend_timeout_seconds,
        )
    except httpx.RequestError as exc:
        raise UpstreamSystemError(SYSTEM_NAME, f"Could not reach pricing system: {exc}") from exc

    if response.status_code == 404:
        raise UpstreamNotFoundError(SYSTEM_NAME, f"No pricing record for SKU '{sku}'")
    if response.status_code != 200:
        raise UpstreamSystemError(SYSTEM_NAME, f"Unexpected pricing response (status {response.status_code})")

    data = response.json()
    return PricingRaw(
        sku=data["sku"],
        discount_percent=data["discount_percent"],
        promo_active=data["promo_active"],
    )
