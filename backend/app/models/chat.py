from pydantic import BaseModel
from contracts import Citation


class ChatRequest(BaseModel):
    query: str
    machine_id: str
    session_id: str|None = None  #The session_id is created after the first turn of conversation

class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation] = []
    session_id: str  
