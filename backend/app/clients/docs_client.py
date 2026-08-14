from contracts import SearchDocsResponse
from app.clients.base import HttpAgentClient


class DocsClient(HttpAgentClient[SearchDocsResponse]):
    path = "/agents/docs/search"
    response_schema = SearchDocsResponse
    agent_name = "Docs"