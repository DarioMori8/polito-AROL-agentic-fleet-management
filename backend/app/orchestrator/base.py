from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator
from uuid import UUID

from app.db.models import User
from app.models.chat import ChatRequest, ChatResponse, ConversationHistory


# --- Domain errors
#
# Raised by prepare_turn(). They say WHAT went wrong in domain terms; the HTTP
# layer decides the status code. This keeps the orchestrator free of FastAPI.

class MachineNotFoundError(Exception):
    """The machine does not exist, or belongs to another company."""


class ConversationNotFoundError(Exception):
    """The thread does not exist, belongs to another user, or to another machine."""


@dataclass(frozen=True)
class TurnContext:
    """
    Everything a turn needs, already validated. Built by prepare_turn()
    before any response is started; the execution phase trusts it blindly.
    """
    thread_id: UUID
    user_id: str
    company_id: str
    machine_id: str
    is_new: bool          # True on the first turn of a new conversation


class Orchestrator(ABC):
    """
    The contract between the HTTP layer and the conversational engine.

    A turn has two phases:
      1. prepare_turn — checks that can fail because of the request
         (machine ownership, thread ownership). Runs before the response.
      2. handle / handle_stream — runs the engine on a validated context.
    """

    @abstractmethod
    async def prepare_turn(self, user: User, request: ChatRequest) -> TurnContext:
        ...

    @abstractmethod
    async def handle(self, context: TurnContext, query: str) -> ChatResponse:
        ...

    @abstractmethod
    def handle_stream(self, context: TurnContext, query: str) -> AsyncIterator[dict]:
        ...

    @abstractmethod
    async def get_history(self, user: User, thread_id: UUID) -> ConversationHistory | None:
        ...
