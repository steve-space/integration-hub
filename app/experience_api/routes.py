"""
Experience API layer: the outward-facing contract for a specific consumer
— here, a storefront frontend.

This layer is deliberately thin: it translates HTTP concerns (status
codes, request/response shapes) and delegates all real work to the
Process API. It never talks to a backend system directly, and it never
contains business rules — if you find yourself writing an `if` about
stock or pricing logic here, that logic belongs one layer down instead.
"""
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from app.exceptions import ProductNotFoundError, UpstreamSystemError
from app.process_api.inventory_service import get_product_availability

router = APIRouter(tags=["experience-api"])


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


@router.get("/products/{sku}/availability")
async def get_availability(sku: str, client: httpx.AsyncClient = Depends(get_http_client)) -> dict:
    try:
        return await get_product_availability(sku, client)
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UpstreamSystemError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Upstream system '{exc.system}' is currently unavailable — please try again shortly.",
        ) from exc
