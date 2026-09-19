"""
Integration Hub — the Process/Experience API application.

Architecture (API-led connectivity, the same layering MuleSoft's Anypoint
Platform promotes):

    Storefront  ─────▶  Experience API  ─────▶  Process API  ─────▶  System APIs  ─────▶  Backends
    (consumer)          (this app's           (orchestration,        (warehouse_client,    (legacy_warehouse,
                          HTTP routes)          merging, rules)        pricing_client)        legacy_pricing)

See docs/SOLUTION_DESIGN.md for the full architecture write-up and a diagram.
"""

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.experience_api.routes import router as experience_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One shared HTTP client, reused across every request, rather than
    # opening a brand new TCP connection to each backend per call.
    app.state.http_client = httpx.AsyncClient()
    yield
    await app.state.http_client.aclose()


app = FastAPI(
    title="Integration Hub",
    description=(
        "Experience API for a jewelry storefront: combines stock data from a "
        "legacy SOAP/XML warehouse system and pricing/promotion data from a "
        "modern REST system into one unified product-availability response."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(experience_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


"""
The API is designed to be deployed as a single FastAPI app, with a single
HTTP client shared across all requests. This is a deliberate design choice
to minimize the number of TCP connections we need to open to the backend
systems, and to keep the app as simple and stateless as possible.
"""
