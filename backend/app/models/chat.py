from pydantic import BaseModel
from enum import Enum


class ChatRequest(BaseModel):
    query: str
    machine_id: str
    session_id: str|None = None  #The session_id is created after the first turn of conversation

class ChatResponse(BaseModel):
    answer: str
    sources: list[dict] = []
    session_id: str  



class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"

class HistoryMessage(BaseModel):
    role: MessageRole                       # "user" | "assistant"
    content: str
    sources: list[dict] = []  # always present; empty for user messages and citation-less answers


class ConversationHistory(BaseModel):
    session_id: str
    messages: list[HistoryMessage]