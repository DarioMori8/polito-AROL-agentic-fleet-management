import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.chat import ChatRequest, ChatResponse
from app.orchestrator.orchestrator import LangGraphOrchestrator


router = APIRouter(prefix="/v1", tags=["chat"])

orchestrator = LangGraphOrchestrator()
 
 
@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest) -> ChatResponse:
    return await orchestrator.handle(payload)



def _sse_format(event: dict) -> str:
    """
    Serializes one event dict into the SSE wire format:
        event: <type>
        data: <json>
        <blank line>
    ensure_ascii=False keeps accented characters (Italian) intact.
    """
    event_type = event.get("type", "message")
    data = json.dumps(event, ensure_ascii=False)
    return f"event: {event_type}\ndata: {data}\n\n"


@router.post("/chat/stream")
async def chat_stream_endpoint(payload: ChatRequest) -> StreamingResponse:
    async def event_generator():
        async for event in orchestrator.handle_stream(payload):
            yield _sse_format(event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disables proxy buffering (nginx)
        },
    )