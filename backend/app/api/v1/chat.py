from fastapi import APIRouter
from app.models.chat import ChatRequest, ChatResponse
from app.orchestrator.orchestrator import LangGraphOrchestrator


router = APIRouter(prefix="/v1", tags=["chat"])

orchestrator = LangGraphOrchestrator()
 
 
@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest) -> ChatResponse:
    return await orchestrator.handle(payload)