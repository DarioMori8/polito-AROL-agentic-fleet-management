from pydantic import BaseModel


class SearchManualTask(BaseModel):
    query: str
    machine_id: str

class Citation(BaseModel):
    doc: str
    page: int
    snippet: str

class SearchManualResponse(BaseModel):
    answer: str
    citations: list[Citation] = []
    confidence: float