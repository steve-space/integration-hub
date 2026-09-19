# Integration Hub

A small, complete example of **API-led connectivity** — the same
architecture pattern MuleSoft's Anypoint Platform is built around —
implemented in plain Python/FastAPI instead of Mule runtime, to
demonstrate the *pattern* rather than one specific vendor's tooling.

It connects two independent backend systems (a legacy SOAP/XML warehouse
system and a modern REST/JSON pricing system) into one clean REST API for
a storefront frontend: *"is this product in stock, and what does it cost
right now, including any active promotion?"*

📖 **New to this pattern?** Read [`LEARNING_GUIDE.md`](LEARNING_GUIDE.md) —
a full, beginner-friendly walkthrough of every concept, command, and file
in this project.

## Architecture

```
Storefront ──▶ Experience API ──▶ Process API ──▶ System APIs ──▶ Backends
                                                                    ├─ Warehouse (SOAP/XML)
                                                                    └─ Pricing (REST/JSON)
```

Full write-up: [`docs/SOLUTION_DESIGN.md`](docs/SOLUTION_DESIGN.md).
Field-by-field transformation rules: [`docs/MAPPING_SPECIFICATION.md`](docs/MAPPING_SPECIFICATION.md).
API contract (RAML): [`docs/api-specs/experience-api.raml`](docs/api-specs/experience-api.raml).
Agile backlog translation: [`docs/USER_STORIES.md`](docs/USER_STORIES.md).
Review checklist: [`docs/CODE_REVIEW_CHECKLIST.md`](docs/CODE_REVIEW_CHECKLIST.md).

## Endpoint

```
GET /products/{sku}/availability
```

```json
{
  "sku": "WM-1001",
  "product_name": "Wempe Iron Diver Chronograph",
  "in_stock": true,
  "quantity_available": 12,
  "currency": "EUR",
  "base_price": 4999.0,
  "discount_percent": 10,
  "promo_active": true,
  "final_price": 4499.1,
  "warehouse_location": "HH-01"
}
```

## Stack

- **FastAPI + httpx** — the integration layer and its two mock backend systems
- **XML parsing** (`xml.etree.ElementTree`) — for the legacy SOAP-style warehouse system
- **pytest + respx** — 15 tests: pure mapping-function unit tests, System API tests with mocked HTTP, and full Experience API tests (success, not-found, both backend-down scenarios)
- **Docker + docker-compose** — all three services run together, wired by service name
- **GitHub Actions** — CI runs the test suite and builds the Docker image on every push

## Running locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Terminal 1: legacy warehouse system (SOAP-style XML)
uvicorn legacy_warehouse.main:app --port 9001

# Terminal 2: pricing & promotions system (REST/JSON)
uvicorn legacy_pricing.main:app --port 9002

# Terminal 3: the integration hub itself
uvicorn app.main:app --reload
```

```bash
curl http://localhost:8000/products/WM-1001/availability
curl http://localhost:8000/products/WM-2002/availability   # out of stock
curl -i http://localhost:8000/products/UNKNOWN/availability  # 404
```

## Running with Docker

```bash
docker compose up --build
```

Starts all three services together, correctly networked. Hub available at `http://localhost:8000`.

## Tests

```bash
pytest -v
```

15 tests. None of them make a real network call — the two backend
systems are mocked with `respx` — so the suite runs in well under a
second with no setup required.

## Why this project exists

Built specifically to demonstrate the skill set behind an
**Integration Architect** role: API-led connectivity architecture,
REST/SOAP API design, contract specification (RAML), explicit data
mapping/transformation rules (the same role DataWeave plays in MuleSoft),
solution design documentation, a code review checklist, and user stories
translating a technical design into an engineering backlog.
