from contracts import SearchManualResponse
from app.clients.base import HttpAgentClient


class ManualsClient(HttpAgentClient[SearchManualResponse]):
    path = "/agents/manuals/search"
    response_schema = SearchManualResponse
    agent_name = "Manuals"
