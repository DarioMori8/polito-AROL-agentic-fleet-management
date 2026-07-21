from fastapi import APIRouter
from app.clients.manuals_client import ManualsClient
from app.models.chat import ChatRequest, ChatResponse
from app.orchestrator.llm_adapter import get_orchestrator_llm
from app.orchestrator.orchestrator import LLMOrchestrator


router = APIRouter(prefix="/v1", tags=["chat"])

orchestrator = LLMOrchestrator(llm=get_orchestrator_llm())

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest):
    return await orchestrator.handle(payload)