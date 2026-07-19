from pydantic import BaseModel


class SearchManualTask(BaseModel):
    """Request payload sent to the Manuals Agent's /agents/manuals/search endpoint."""
    query: str
    machine_id: str


class Citation(BaseModel):
    """A single source reference backing an agent's answer."""
    doc: str
    page: int
    snippet: str


class SearchManualResponse(BaseModel):
    """Response returned by the Manuals Agent."""
    answer: str
    citations: list[Citation] = []
    confidence: float