import json

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse

from app.models.chat import ChatRequest, ChatResponse, ConversationHistory

# ... router già esistente ...

router = APIRouter(prefix="/v1", tags=["chat"])

 
 
@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest, request: Request) -> ChatResponse:
    orchestrator= request.app.state.orchestrator
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
async def chat_stream_endpoint(payload: ChatRequest, request:Request) -> StreamingResponse:
    async def event_generator():
        orchestrator= request.app.state.orchestrator
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




@router.get("/conversations/{session_id}/messages", response_model=ConversationHistory)
async def get_conversation_history(
    session_id: str,
    request: Request,
) -> ConversationHistory:
    orchestrator = request.app.state.orchestrator

    # (auth will slot in here later: "does the caller own this thread?" —
    #  a guard between receiving the id and reading the data, touching neither.)

    history = await orchestrator.get_history(session_id)
    if history is None:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation '{session_id}' not found",
        )
    return history