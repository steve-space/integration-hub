"""Shared error types used across the integration layers.

Keeping these independent of any one layer (System API / Process API /
Experience API) lets each layer catch exactly the failure modes it cares
about, without importing internals from another layer.
"""


class UpstreamNotFoundError(Exception):
    """The backend system was reachable and answered, but has no record
    for the requested key (e.g. an unknown SKU)."""

    def __init__(self, system: str, message: str):
        self.system = system
        super().__init__(message)


class UpstreamSystemError(Exception):
    """The backend system is unreachable, timed out, or returned an
    unexpected/malformed response — a genuine outage or fault, as opposed
    to a normal 'not found' business answer."""

    def __init__(self, system: str, message: str):
        self.system = system
        super().__init__(message)


class ProductNotFoundError(Exception):
    """The Process API's final verdict: this product does not exist,
    according to the authoritative system (the warehouse)."""
