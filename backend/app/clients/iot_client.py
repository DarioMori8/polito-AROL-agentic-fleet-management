from contracts import SearchIoTResponse
from app.clients.base import HttpAgentClient


class IoTClient(HttpAgentClient[SearchIoTResponse]):
    path = "/agents/iot/search"
    response_schema = SearchIoTResponse
    agent_name = "IoT"