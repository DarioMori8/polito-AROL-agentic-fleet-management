from abc import ABC, abstractmethod

from app.models.chat import ChatRequest, ChatResponse


class Orchestrator(ABC):

    """
    Could be necessities to implement morerouting strategy
    """
    @abstractmethod
    async def handle(seld, request:ChatRequest)-> ChatResponse:
        ...
