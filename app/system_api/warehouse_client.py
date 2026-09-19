"""
System API layer: the warehouse system.

A System API's job (in API-led connectivity terms) is to be a thin,
*faithful* wrapper around one backend — it speaks that backend's native
protocol (here: SOAP-style XML over HTTP) and exposes its data using the
backend's own field names and types, completely unchanged. No renaming,
no unit conversion, no business logic — that all belongs one layer up, in
the transform/process layers. Keeping this layer "dumb on purpose" means
if the warehouse system is ever replaced, only this one file has to change.
"""
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import httpx

from app.config import settings
from app.exceptions import UpstreamNotFoundError, UpstreamSystemError

SYSTEM_NAME = "warehouse"


@dataclass
class WarehouseStockRaw:
    """Fields exactly as the legacy system names and types them —
    deliberately NOT renamed to anything friendlier at this layer."""

    sku: str
    article_name: str
    qty_on_hand: int
    unit_price_cents: int
    currency: str
    warehouse_location: str


async def fetch_stock(sku: str, client: httpx.AsyncClient) -> WarehouseStockRaw:
    request_xml = f"<GetStockRequest><Sku>{sku}</Sku></GetStockRequest>"

    try:
        response = await client.post(
            f"{settings.warehouse_system_url}/WarehouseService",
            content=request_xml,
            headers={"Content-Type": "application/xml"},
            timeout=settings.backend_timeout_seconds,
        )
    except httpx.RequestError as exc:
        raise UpstreamSystemError(SYSTEM_NAME, f"Could not reach warehouse system: {exc}") from exc

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError as exc:
        raise UpstreamSystemError(SYSTEM_NAME, f"Warehouse system returned unparseable XML: {exc}") from exc

    if root.tag == "Fault":
        code = root.findtext("Code", default="")
        message = root.findtext("Message", default="Unknown fault")
        if code == "SKU_NOT_FOUND":
            raise UpstreamNotFoundError(SYSTEM_NAME, message)
        raise UpstreamSystemError(SYSTEM_NAME, f"Warehouse system fault [{code}]: {message}")

    if response.status_code != 200 or root.tag != "StockResponse":
        raise UpstreamSystemError(SYSTEM_NAME, f"Unexpected warehouse response (status {response.status_code})")

    return WarehouseStockRaw(
        sku=root.findtext("Sku", default=sku),
        article_name=root.findtext("ArticleName", default=""),
        qty_on_hand=int(root.findtext("QtyOnHand", default="0")),
        unit_price_cents=int(root.findtext("UnitPriceCents", default="0")),
        currency=root.findtext("Currency", default="EUR"),
        warehouse_location=root.findtext("WarehouseLocation", default=""),
    )
