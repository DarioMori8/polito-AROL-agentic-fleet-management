from fastapi import APIRouter
from app.models.chat import ChatRequest
router = APIRouter(prefix="/v1", tags=["chat"])


@router.post("/chat")
def prova_chat(payload: ChatRequest):
    return {"query": payload.query, "machine_id": payload.machine_id}