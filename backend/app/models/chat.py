from enum import Enum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, StringConstraints


# Upper bound on a single user message. The orchestrator's context window is
# ORCHESTRATOR_NUM_CTX tokens and the system prompt already takes part of it:
# an oversized query would crowd out the tool results the answer depends on.
MAX_QUERY_CHARS = 2000

# Whitespace is stripped BEFORE the length checks, so "   " counts as empty
# and is rejected like "" — both with a 422, before the graph ever runs.
QueryText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_QUERY_CHARS),
]


class ChatRequest(BaseModel):
    query: QueryText
    machine_id: str
    # Absent on the first turn: the server mints a new thread and returns its
    # id, which the client sends back on every following turn. Typed as UUID so
    # that anything else (e.g. an invented "abc") is rejected with a 422.
    # Ownership is NOT checked here: a well-formed id can still belong to
    # someone else — that check needs the DB and lives in the orchestrator.
    thread_id: UUID | None = None


class Denial(BaseModel):
    """
    A tool call refused by the access model in this turn. Produced by code,
    not by the LLM: the client can show it as a distinct notice without
    interpreting the answer text.
    """
    tool: str
    domain: str
    message: str


class ChatResponse(BaseModel):
    answer: str
    # Untyped for now: to be replaced by a discriminated union on `kind`,
    # matching what normalize_artifact() produces.
    sources: list[dict] = []
    denied: list[Denial] = []
    thread_id: UUID


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class HistoryMessage(BaseModel):
    role: MessageRole
    content: str
    # Always present; empty for user messages and for citation-less answers.
    # (Pydantic copies mutable defaults per instance: [] is safe here.)
    sources: list[dict] = []
    # Access denials that occurred in the turn this answer closes.
    denied: list[Denial] = []


class ConversationHistory(BaseModel):
    thread_id: UUID
    # A thread is bound to one machine for its whole life: returned so that a
    # client reopening an old conversation knows which machine it is about.
    machine_id: str
    messages: list[HistoryMessage]
