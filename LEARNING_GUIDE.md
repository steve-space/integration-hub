# Integration Hub — Learning Guide

This project was built specifically to map onto the skills listed in a
real **Junior Integration Architect** job posting (systems integration,
REST/SOAP API design, MuleSoft-style architecture, RAML API
specification, DataWeave-style data mapping, solution design
documentation, code review, and agile user stories). This guide explains
every concept, command, and piece of code — and, throughout, calls out
exactly which job requirement each part is meant to demonstrate.

## Table of contents

1. [What is this project, and why does it exist?](#1-what-is-this-project-and-why-does-it-exist)
2. [MuleSoft/Anypoint concepts, explained without MuleSoft](#2-mulesoftanypoint-concepts-explained-without-mulesoft)
3. [How the project was built, step by step](#3-how-the-project-was-built-step-by-step)
4. [Running it yourself](#4-running-it-yourself)
5. [How the tests work](#5-how-the-tests-work)
6. [The documentation set, and which job skill each file proves](#6-the-documentation-set-and-which-job-skill-each-file-proves)
7. [What to remember / talk about in an interview](#7-what-to-remember--talk-about-in-an-interview)

---

## 1. What is this project, and why does it exist?

A **Junior Integration Architect** doesn't usually build brand-new
applications from scratch — the job is to sit *between* business needs
and existing systems, and design how those systems talk to each other
without forcing anyone to rewrite them. This project simulates exactly
that situation on a small scale:

- A **legacy warehouse system** that only understands SOAP-style XML
  (common in older enterprise software — replacing it would be
  expensive and risky, so it stays, and everything new has to work
  *around* it).
- A **modern pricing system** that speaks REST/JSON (a newer service,
  built independently, with no knowledge of the warehouse system).
- A **storefront** that needs one simple question answered: *"is this
  product in stock, and what's the price right now?"* — without needing
  to know either backend system exists.

The project builds the **integration layer** in the middle: it talks to
both backends in their own language, combines their answers, and exposes
one clean API to the storefront.

## 2. MuleSoft/Anypoint concepts, explained without MuleSoft

The job posting is specifically about **MuleSoft's Anypoint Platform** —
a commercial, Java-based integration platform. This project doesn't use
MuleSoft itself (it's paid enterprise software, not something to install
casually), but implements the exact same *architectural pattern* MuleSoft
is built around, using plain Python. The ideas transfer directly — a
Junior Integration Architect job is fundamentally about understanding
this pattern, not about memorizing one vendor's UI.

| MuleSoft/Anypoint term | What it means | Where it is in this project |
|---|---|---|
| **API-led connectivity** | A layered approach: System APIs (talk to one backend each), Process APIs (combine/orchestrate them), Experience APIs (tailored to one consumer) | `app/system_api/`, `app/process_api/`, `app/experience_api/` — three separate folders, one per layer |
| **System API** | A thin API that wraps exactly one backend system, unchanged | `warehouse_client.py`, `pricing_client.py` |
| **Process API** | Combines multiple System APIs and applies business rules | `inventory_service.py` |
| **Experience API** | The API a specific consumer (here: a storefront) actually calls | `experience_api/routes.py` |
| **DataWeave** | MuleSoft's language for writing data transformation/mapping scripts between one data shape and another | `app/transform/mappings.py` — plain Python functions doing the same job, documented the same way DataWeave scripts would be |
| **RAML** | "RESTful API Modeling Language" — a way to *specify* an API's shape (endpoints, request/response fields, examples) before or alongside building it | `docs/api-specs/experience-api.raml` |
| **SOAP** | An older, XML-based protocol for web services, still common in enterprise/legacy systems | Simulated by `legacy_warehouse/main.py` |
| **Solution design** | A written architecture document explaining *why* an integration is structured the way it is, for other engineers and architects to review | `docs/SOLUTION_DESIGN.md` |

## 3. How the project was built, step by step

### Step 1 — Folder structure matching the architecture layers

```bash
mkdir -p integration-hub/{legacy_warehouse,legacy_pricing,app/system_api,app/transform,app/process_api,app/experience_api,tests,docs/api-specs,.github/workflows}
```

Notice the folder structure **is** the architecture diagram — this is
deliberate. Anyone opening this project sees the API-led layering just
from the folder names, before reading a single line of code.

### Step 2 — The two mock backend systems

`legacy_warehouse/main.py` simulates the SOAP-style system. A few
specific, realistic details worth understanding:

```python
@app.post("/WarehouseService")
async def warehouse_service(request: Request) -> Response:
    ...
    if record is None:
        fault_xml = "<Fault><Code>SKU_NOT_FOUND</Code>...</Fault>"
        return Response(content=fault_xml, status_code=500, media_type="application/xml")
```

Real SOAP services commonly return **HTTP 500 with a `<Fault>` XML body**
even for an ordinary business situation like "no such record" — not a
clean `404`. This is one of the most important, easy-to-miss realities
of working with legacy SOAP systems: **you cannot trust the HTTP status
code alone; you have to parse the response body to know what actually
happened.** This project deliberately reproduces that quirk so the
integration layer has to handle it correctly (see Step 4).

`legacy_pricing/main.py` is a normal modern REST/JSON service, with
ordinary `404` behavior — included specifically to contrast with the
warehouse system, since a real Integration Architect works with a mix of
old and new systems side by side, not just one style.

### Step 3 — The System API layer: thin, faithful wrappers

```python
# app/system_api/warehouse_client.py
@dataclass
class WarehouseStockRaw:
    sku: str
    article_name: str      # NOT renamed to "product_name" here
    qty_on_hand: int        # NOT converted to a boolean here
    unit_price_cents: int    # NOT converted to euros here
    ...
```

The field names here **exactly match the legacy system's own
vocabulary** — `article_name`, not `product_name`; `unit_price_cents`,
not `price`. This is the core discipline of a System API: it doesn't
try to make the data "nicer" yet. That's a separate, explicit step (the
transform layer), because mixing "talk to the backend" and "make the
data meaningful" in one place makes both harder to change independently.

Parsing the XML response:

```python
root = ET.fromstring(response.text)
if root.tag == "Fault":
    code = root.findtext("Code", default="")
    if code == "SKU_NOT_FOUND":
        raise UpstreamNotFoundError(SYSTEM_NAME, message)
    raise UpstreamSystemError(SYSTEM_NAME, f"Warehouse system fault [{code}]: {message}")
```

This is exactly the "don't trust the status code" handling mentioned in
Step 2: the code looks *inside* the XML body to decide whether this is a
normal "not found" (→ a clean `404` eventually) or a genuine system fault
(→ a `502`). Two **custom exception types**
(`UpstreamNotFoundError`, `UpstreamSystemError`, in `app/exceptions.py`)
make that distinction explicit and impossible to accidentally blur later
in the code.

### Step 4 — The transform layer: the DataWeave equivalent

```python
# app/transform/mappings.py
def map_warehouse_stock(raw: WarehouseStockRaw) -> dict:
    return {
        "sku": raw.sku,
        "product_name": raw.article_name,               # renamed
        "quantity_available": raw.qty_on_hand,
        "in_stock": raw.qty_on_hand > 0,                  # derived
        "base_price": round(raw.unit_price_cents / 100, 2), # unit-converted
        ...
    }
```

*Now* the renaming and conversion happens — in one dedicated, pure
function, with every single rule also written out in plain English in
`docs/MAPPING_SPECIFICATION.md`. In a real MuleSoft project, this exact
logic (rename a field, convert cents to euros, derive a boolean from a
quantity) is what a **DataWeave script** does — DataWeave is just a
domain-specific language built for exactly this kind of transformation,
the same job this Python function does here.

`merge_product_availability` then combines the *two* transformed
fragments (stock + pricing) into the final shape — this two-step
"transform each source independently, then merge" pattern scales cleanly
to more sources later (see Solution Design §7).

### Step 5 — The Process API: orchestration and business rules

```python
# app/process_api/inventory_service.py
stock_result, pricing_result = await asyncio.gather(
    fetch_stock(sku, client),
    fetch_pricing(sku, client),
    return_exceptions=True,
)
```

Both backend systems are called **at the same time**
(`asyncio.gather`), not one after another — there's no reason to make the
storefront wait twice as long for two independent lookups.
`return_exceptions=True` means if one of the two calls raises an
exception, `asyncio.gather` doesn't immediately crash the whole
function — it hands back the exception *as a value* instead, so the code
can inspect both results and decide, individually, what to do about each one.

The interesting design decision is what happens next:

```python
if isinstance(stock_result, UpstreamNotFoundError):
    raise ProductNotFoundError(...)
...
if isinstance(pricing_result, (UpstreamNotFoundError, UpstreamSystemError)):
    pricing = None   # fall back gracefully — see below
```

The **warehouse** result is treated as critical — any failure there fails
the whole operation. The **pricing** result is treated as optional — any
failure there just means "no discount known," and the request still
succeeds. This is a genuine, common integration-architecture decision:
**not every dependency deserves the same failure behavior**, and a good
integration layer makes that choice deliberately and explicitly (written
down in `docs/SOLUTION_DESIGN.md` §4), not by accident.

### Step 6 — The Experience API: a thin HTTP-facing layer

```python
# app/experience_api/routes.py
@router.get("/products/{sku}/availability")
async def get_availability(sku: str, client=Depends(get_http_client)) -> dict:
    try:
        return await get_product_availability(sku, client)
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UpstreamSystemError as exc:
        raise HTTPException(status_code=502, detail=f"Upstream system '{exc.system}' is currently unavailable...") from exc
```

Notice how little this function does: call the Process API, and
translate its two possible exceptions into the two matching HTTP status
codes. No business logic lives here at all — if a future change needed
to add an `if` about stock or pricing *here*, that would be a sign the
logic belongs one layer down instead.

### Step 7 — Writing the tests, one per layer

Following the same "test each layer at the right level" idea from the
`CODE_REVIEW_CHECKLIST.md`:

- `tests/test_transform.py` — pure function tests, no network, no app at
  all. Fastest possible tests, for the mapping rules specifically.
- `tests/test_system_api.py` — uses the **`respx`** library to intercept
  `httpx` calls and return fake responses (including a fake SOAP Fault
  and a simulated connection failure), testing the real XML/JSON parsing
  code without a real network call.
- `tests/test_experience_api.py` — full end-to-end tests through FastAPI's
  `TestClient`, with both backends mocked via `respx`, proving the whole
  chain (HTTP in → System APIs → transform → merge → HTTP out) works
  together — including the two resilience behaviors (hard failure on
  warehouse-down, graceful fallback on pricing-down) that are the whole
  point of this project's design.

```bash
pip install -r requirements.txt
pytest -v   # 15 passed
```

### Step 8 — Verifying it live, not just under mocked tests

Beyond the 15 automated tests, all **three real services** were started
as actual separate processes and driven with real `curl` requests —
proving the whole thing works end-to-end, not just against fakes:

```bash
uvicorn legacy_warehouse.main:app --port 9001 &
uvicorn legacy_pricing.main:app --port 9002 &
uvicorn app.main:app --port 8010 &

curl http://localhost:8010/products/WM-1001/availability
# → real merged JSON, discount correctly applied
```

Then, specifically to prove the graceful-degradation design decision
actually works and isn't just a nice idea in the docs, the pricing
service was **killed while the hub kept running**, and the same request
was repeated:

```bash
pkill -f "uvicorn legacy_pricing.main:app"
curl http://localhost:8010/products/WM-1001/availability
# → still 200 OK, promo_active: false, final_price == base_price
```

This is a good habit for any integration work: **don't just trust that
your error-handling code is correct because you wrote it carefully —
actually break the thing it's supposed to handle, and watch it recover.**

## 4. Running it yourself

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

uvicorn legacy_warehouse.main:app --port 9001   # terminal 1
uvicorn legacy_pricing.main:app --port 9002     # terminal 2
uvicorn app.main:app --reload                    # terminal 3

curl http://localhost:8000/products/WM-1001/availability
```

Or with Docker (all three services together):

```bash
docker compose up --build
```

## 5. How the tests work

```bash
pytest -v
```

15 tests across three files (see Step 7 above for what each level
covers). None of them touch a real network — `respx` intercepts every
`httpx` call — so the suite runs in well under a second and needs no
setup.

## 6. The documentation set, and which job skill each file proves

| File | Job requirement it demonstrates |
|---|---|
| [`docs/SOLUTION_DESIGN.md`](docs/SOLUTION_DESIGN.md) | *"Integrations-Konzeption... technische Solution Designs"* — a written architecture document with diagrams and explicit trade-off reasoning |
| [`docs/MAPPING_SPECIFICATION.md`](docs/MAPPING_SPECIFICATION.md) | *"detaillierte Mapping Regeln mithilfe von Dataweave"* — the same field-by-field mapping documentation, implemented in Python instead of DataWeave |
| [`docs/api-specs/experience-api.raml`](docs/api-specs/experience-api.raml) | *"APIs im RAML-Format entwerfen und dokumentieren"* — a hand-written RAML 1.0 spec |
| [`docs/USER_STORIES.md`](docs/USER_STORIES.md) | *"Designs in klare, umsetzbare User Stories... übersetzen"* — the solution design translated into a backlog |
| [`docs/CODE_REVIEW_CHECKLIST.md`](docs/CODE_REVIEW_CHECKLIST.md) | *"Code Reviews... durchführen, um die Einhaltung unserer Best Practices... zu gewährleisten"* — a concrete review checklist, then applied to this project's own code as a self-review |

## 7. What to remember / talk about in an interview

- **The layering is the point**: System APIs are "dumb on purpose,"
  Process APIs own orchestration and business rules, Experience APIs stay
  thin and consumer-facing. Being able to say *why* each layer exists —
  not just that it does — is what separates "I copied a folder
  structure" from "I understand API-led connectivity."
- **SOAP's HTTP-status-doesn't-mean-what-you-think quirk**, and handling
  it by parsing the response body, not trusting the status code.
- **Not every dependency deserves the same failure behavior** — the
  warehouse-is-critical / pricing-is-optional distinction, made
  explicitly and tested, not accidental.
- **Concurrent orchestration** (`asyncio.gather`) instead of unnecessarily
  serial backend calls.
- **Documentation as a first-class deliverable**, not an afterthought —
  solution design, mapping spec, RAML, user stories, and a review
  checklist all exist because a real Integration Architect produces
  exactly these artifacts, not just working code.
- **Honesty about what wasn't done**: the code review checklist itself
  names a deliberate gap (no retry logic) rather than hiding it — a
  genuinely useful interview talking point about how you scope and
  communicate trade-offs.
