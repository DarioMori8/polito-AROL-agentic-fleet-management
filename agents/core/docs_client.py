import httpx

from core.config import settings


def _normalize_enum(value: str | None) -> str | None:
    """Coerce an LLM-supplied filter value to the backend's enum spelling.

    Tool schemas declare enums, but a model may still answer "spare parts" or
    "In Production" where the data says "spare_parts". The backend is a stand-in
    for a real ERP and stays strict, so the tolerance lives here, on the seam.
    """
    if value is None:
        return None
    return value.strip().lower().replace(" ", "_").replace("-", "_")


class DocsClient:
    """HTTP client for the backoffice service (mock today, real ERP/CRM/Document Store later).

    Only the base URL and auth headers change when swapping mock for real —
    this class is the seam DocsAgent depends on, never the raw data source.
    """

    def __init__(self):
        self.base_url = settings.DOCS_SERVICE_URL

    async def search_documents(
        self,
        query: str,
        machine_id: str,
        document_type: str | None = None,
        order_id: str | None = None,
    ) -> list[dict]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
            response = await client.post(
                "/documents/search",
                json={
                    "query": query,
                    "machine_id": machine_id,
                    "document_type": _normalize_enum(document_type),
                    "order_id": order_id,
                },
            )
            response.raise_for_status()
            return response.json()["results"]

    async def search_orders(
        self,
        machine_id: str,
        order_id: str | None = None,
        status: str | None = None,
        order_type: str | None = None,
    ) -> list[dict]:
        params = {
            "machine_id": machine_id,
            "order_id": order_id,
            "status": _normalize_enum(status),
            "order_type": _normalize_enum(order_type),
        }
        return await self._get("/orders", params)

    async def search_quotes(
        self,
        machine_id: str,
        quote_id: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        params = {
            "machine_id": machine_id,
            "quote_id": quote_id,
            "status": _normalize_enum(status),
        }
        return await self._get("/quotes", params)

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
