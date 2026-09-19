"""
Mock "pricing & promotions" system.

Represents a second, independent backend system — modern REST/JSON this
time, unlike the warehouse system. This is deliberate: a real Integration
Architect rarely connects to just one backend. A storefront's "is this
product available, and at what price?" question typically needs data
merged from *multiple* systems (here: stock from the warehouse, discounts
from a separate promotions engine) that were never designed to know about
each other.
"""
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Legacy Pricing & Promotions System (mock REST backend)")

PROMOTIONS_DB = {
    "WM-1001": {"discount_percent": 10, "promo_active": True},
    "WM-2002": {"discount_percent": 0, "promo_active": False},
}


@app.get("/pricing/{sku}")
async def get_pricing(sku: str) -> dict:
    record = PROMOTIONS_DB.get(sku)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No pricing record for SKU '{sku}'")
    return {"sku": sku, **record}
