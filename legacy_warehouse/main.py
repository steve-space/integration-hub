"""
Mock "legacy" warehouse system.

Stands in for an old-style backend that speaks SOAP/XML over HTTP instead
of a modern JSON REST API — exactly the kind of system a real Integration
Architect has to connect to, because it's too expensive/risky for the
business to replace it, but new applications (like a storefront) can't be
built to understand its internal XML format directly.

Deliberately mimics two real SOAP quirks:
  1. The request/response bodies are XML, not JSON.
  2. Business errors (e.g. "no such SKU") come back as HTTP 500 with a
     <Fault> body, NOT as a clean HTTP 404 — this is a very common,
     annoying real-world SOAP behavior that an integration layer has to
     handle explicitly (you can't just trust the HTTP status code).
"""
from fastapi import FastAPI, Request, Response

app = FastAPI(title="Legacy Warehouse System (mock SOAP-style backend)")

# In-memory "database" of stock records, keyed by SKU.
STOCK_DB = {
    "WM-1001": {
        "article_name": "Wempe Iron Diver Chronograph",
        "qty_on_hand": 12,
        "unit_price_cents": 499900,
        "currency": "EUR",
        "warehouse_location": "HH-01",
    },
    "WM-2002": {
        "article_name": "Wempe Pearl Necklace",
        "qty_on_hand": 0,
        "unit_price_cents": 189000,
        "currency": "EUR",
        "warehouse_location": "HH-01",
    },
}


@app.post("/WarehouseService")
async def warehouse_service(request: Request) -> Response:
    body = (await request.body()).decode("utf-8")
    sku = _extract_tag(body, "Sku")

    record = STOCK_DB.get(sku)
    if record is None:
        fault_xml = (
            "<Fault>"
            "<Code>SKU_NOT_FOUND</Code>"
            f"<Message>No stock record for SKU '{sku}'</Message>"
            "</Fault>"
        )
        # Real SOAP services typically return 500 for a SOAP Fault, even
        # for what is really just a "not found" business condition.
        return Response(content=fault_xml, status_code=500, media_type="application/xml")

    response_xml = (
        "<StockResponse>"
        f"<Sku>{sku}</Sku>"
        f"<ArticleName>{record['article_name']}</ArticleName>"
        f"<QtyOnHand>{record['qty_on_hand']}</QtyOnHand>"
        f"<UnitPriceCents>{record['unit_price_cents']}</UnitPriceCents>"
        f"<Currency>{record['currency']}</Currency>"
        f"<WarehouseLocation>{record['warehouse_location']}</WarehouseLocation>"
        "</StockResponse>"
    )
    return Response(content=response_xml, status_code=200, media_type="application/xml")


def _extract_tag(xml_body: str, tag: str) -> str:
    """Tiny, deliberately naive XML tag extractor — good enough for this mock's
    fixed request shape. The real integration layer uses a proper XML parser
    (see app/system_api/warehouse_client.py) — never do it this way for real."""
    start = xml_body.find(f"<{tag}>") + len(tag) + 2
    end = xml_body.find(f"</{tag}>")
    return xml_body[start:end]
