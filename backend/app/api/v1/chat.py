from fastapi import APIRouter
from app.clients.manuals_client import ManualsClient
from app.models.chat import ChatRequest, ChatResponse


router = APIRouter(prefix="/v1", tags=["chat"])

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest):
    client = ManualsClient()
    result = await client.search(payload.query, payload.machine_id)
    return ChatResponse(
        answer=result.answer,
        citations=result.citations,
        session_id="temp-session-id",  # placeholder, vedi discorso sessioni di prima
    )