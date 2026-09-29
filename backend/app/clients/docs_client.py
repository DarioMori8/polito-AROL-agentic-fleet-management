from contracts import SearchDocsResponse, SearchDocsTask

from app.clients.base import HttpAgentClient


class DocsClient(HttpAgentClient[SearchDocsResponse]):
    path = "/agents/docs/search"
    response_schema = SearchDocsResponse
    agent_name = "Docs"

    # Docs is the one agent whose task carries a tenant: it needs company_id
    # on top of the shared (query, machine_id) shape, so it builds its own
    # payload (validated by the shared contract) while still inheriting the
    # transport from _request(). company_id is keyword-only so it can never
    # be passed by position by mistake.
    async def search(  # type: ignore[override]
        self, query: str, machine_id: str, *, company_id: str
    ) -> SearchDocsResponse:
        payload = SearchDocsTask(
            query=query, machine_id=machine_id, company_id=company_id
        ).model_dump()
        return await self._request(payload)
