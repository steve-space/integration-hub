# Code Review Checklist — Integration Layer Changes

A checklist for reviewing changes to this kind of integration codebase —
the sort of design-and-best-practices review a Lead/Integration Architect
runs over a team's pull requests. Organized by the same layers the
architecture is built from, plus cross-cutting concerns.

## Layering discipline

- [ ] Does a **System API** file contain any business logic, unit
      conversion, or field renaming? *(It shouldn't — that belongs in
      `transform/`. A System API should only translate protocol, not meaning.)*
- [ ] Does a **Process API** file call an HTTP client directly, instead of
      going through a System API function? *(It shouldn't — Process APIs
      orchestrate System APIs, they don't talk to backends themselves.)*
- [ ] Does an **Experience API** route contain an `if` about business
      rules (stock, pricing, discounts)? *(It shouldn't — Experience API
      routes translate HTTP only; logic belongs in the Process API.)*

## Mapping / transformation changes

- [ ] Is every new or changed field mapping reflected in
      `docs/MAPPING_SPECIFICATION.md`? *(A mapping rule that exists only
      in code and not in the spec will be wrong within a year.)*
- [ ] Is the mapping function still **pure** (no I/O, no side effects)?
- [ ] Is there a unit test for the new rule, including at least one edge
      case (zero, empty, missing/optional field)?

## Error handling

- [ ] Does every new backend call distinguish **"not found"** (a normal
      business answer) from **"system error"** (a genuine fault)? Mixing
      these up is the single most common integration bug — see
      `system_api/warehouse_client.py` for the SOAP Fault-vs-404 example.
- [ ] Is a timeout set explicitly on every outbound call? *(An
      integration layer with no timeout on a backend call means one slow
      backend can hang your entire service.)*
- [ ] For a new non-critical dependency: is there a documented, tested
      fallback, rather than letting its failure fail the whole request?
      (See Solution Design §4 for the reasoning behind which systems get
      this treatment and which don't.)

## Contracts & documentation

- [ ] If the Experience API's response shape changed, was the RAML/OpenAPI
      spec (`docs/api-specs/`) updated in the same change? *(A spec that
      doesn't match the real API is worse than no spec — consumers will
      trust it.)*
- [ ] Are new endpoints/behaviors reflected as new or updated user stories
      in `docs/USER_STORIES.md`?

## Tests

- [ ] Does the new/changed logic have a test at the **right** level —
      pure-function unit test for mapping rules, mocked-HTTP test for
      System API clients, full-stack test for Experience API behavior?
      (Not everything needs an end-to-end test; not everything is
      adequately covered by only a unit test either.)
- [ ] Do tests cover the failure paths, not just the happy path (backend
      down, backend returns malformed data, resource not found)?

## Security & configuration

- [ ] No secrets, API keys, or internal URLs hardcoded — configuration
      only via environment variables / `.env` (see `app/config.py`).
- [ ] No sensitive data (customer info, prices from a non-public system)
      logged at a verbose level without thinking about where those logs end up.

---

## Self-review: this project against its own checklist

Applying this list to `integration-hub` itself before considering it done:

- ✅ System APIs (`warehouse_client.py`, `pricing_client.py`) contain zero
  business logic — verified by reading them alongside `transform/mappings.py`.
- ✅ Every mapping rule in `mappings.py` has a matching row in
  `MAPPING_SPECIFICATION.md` and a test in `test_transform.py`.
- ✅ "Not found" (`UpstreamNotFoundError`) and "system error"
  (`UpstreamSystemError`) are distinct exception types throughout, checked
  by both `test_system_api.py` and `test_experience_api.py`.
- ✅ Every outbound `httpx` call passes `timeout=settings.backend_timeout_seconds`.
- ✅ The pricing fallback is documented (Solution Design §4) *and* tested
  (`test_availability_still_succeeds_when_pricing_is_down`), not just implemented.
- ⚠️ **Known gap, left deliberate rather than hidden:** there's no retry
  logic on a transient backend failure (a single timeout is treated the
  same as a hard outage) — acceptable for a portfolio-scope project, but
  a real production integration layer would typically add a bounded retry
  with backoff for `UpstreamSystemError`s specifically, not for
  `UpstreamNotFoundError`s (retrying a "not found" answer is pointless).
