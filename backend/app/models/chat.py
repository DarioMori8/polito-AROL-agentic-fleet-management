from pydantic import BaseModel
from app.models.manuals import Citation 

class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation] = []
    session_id: str  


class ChatRequest(BaseModel):
    query: str
    machine_id: str

