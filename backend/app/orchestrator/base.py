from abc import ABC, abstractmethod
from typing import AsyncIterator


from app.models.chat import ChatRequest, ChatResponse


class Orchestrator(ABC):

    """
    Could be necessities to implement morerouting strategy
    """
    @abstractmethod
    async def handle(self, request:ChatRequest)-> ChatResponse:
        ...
    async def handle_stream(self, request: ChatRequest)-> AsyncIterator[dict]:
        ...

