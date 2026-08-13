import httpx

from core.config import settings

# The dataset spells its controlled vocabularies with capitals and spaces. A model
# asked for "still open orders" will happily produce "in_production" or "closed",
# so the spelling is repaired here, on the seam: the backoffice stands in for a
# real ERP and stays strict about the values it accepts.
ORDER_STATUSES = ("Confirmed", "In production", "Delivered", "Closed")
QUOTE_STATUSES = ("Draft", "Submitted", "Superseded", "Approved", "Rejected", "Expired")


def _canonical(value: str | None, vocabulary: tuple[str, ...]) -> str | None:
    if value is None:
        return None
    key = value.strip().lower().replace("_", " ")
    for term in vocabulary:
        if term.lower() == key:
            return term
    # Unknown value: pass it through and let it simply match nothing, rather than
    # silently dropping the filter and widening the result set.
    return value


class DocsClient:
    """HTTP client for the backoffice service (mock today, real ERP/CRM later).

    Only the base URL and auth headers change when swapping mock for real —
    this class is the seam DocsAgent depends on, never the raw data source.
    """

    def __init__(self):
        self.base_url = settings.DOCS_SERVICE_URL

    async def search_orders(
        self,
        company_id: str,
        machine_id: str | None = None,
        order_id: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        return await self._get(
            f"/companies/{company_id}/orders",
            {
                "machine_id": machine_id,
                "order_id": order_id,
                "status": _canonical(status, ORDER_STATUSES),
            },
        )

    async def search_quotes(
        self,
        company_id: str,
        machine_id: str | None = None,
        quote_id: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        return await self._get(
            f"/companies/{company_id}/quotes",
            {
                "machine_id": machine_id,
                "quote_id": quote_id,
                "status": _canonical(status, QUOTE_STATUSES),
            },
        )

    async def list_machines(self) -> list[dict]:
        """The fleet registry, including the serial number of each machine."""
        return await self._get("/machines", {})

    async def _get(self, path: str, params: dict) -> list[dict]:
        # Unset filters are dropped so they are not sent as empty query values.
        params = {k: v for k, v in params.items() if v is not None}
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()["results"]


_client: DocsClient | None = None


def get_docs_client() -> DocsClient:
    global _client
    if _client is None:
        _client = DocsClient()
    return _client
