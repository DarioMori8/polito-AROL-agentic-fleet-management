from abc import ABC, abstractmethod
from typing import AsyncIterator


from app.models.chat import ChatRequest, ChatResponse, ConversationHistory


class Orchestrator(ABC):

    """
    Could be necessities to implement morerouting strategy
    """
    @abstractmethod
    async def handle(self, request:ChatRequest)-> ChatResponse:
        ...
    @abstractmethod
    async def handle_stream(self, request: ChatRequest)-> AsyncIterator[dict]:
        ...
    @abstractmethod
    async def get_history(self, session_id: str) -> ConversationHistory | None:
        ...

