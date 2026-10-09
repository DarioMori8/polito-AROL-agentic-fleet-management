import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.deps import ChatUser
from app.models.chat import ChatRequest, ChatResponse, ConversationHistory, ConversationSummary
from app.orchestrator.base import (
    ConversationNotFoundError,
    MachineNotFoundError,
    Orchestrator,
    TurnContext,
)

router = APIRouter(prefix="/v1", tags=["chat"])


# --- Dependencies

def get_orchestrator(request: Request) -> Orchestrator:
    """
    The orchestrator is built once in the lifespan and kept on app.state.
    Exposing it through a dependency (instead of reading app.state inside each
    endpoint) lets tests swap it with app.dependency_overrides.
    """
    return request.app.state.orchestrator


OrchestratorDep = Annotated[Orchestrator, Depends(get_orchestrator)]


async def _prepare_turn(
    orchestrator: Orchestrator, user: ChatUser, payload: ChatRequest
) -> TurnContext:
    """
    Phase 1 of a turn: every check that can fail because of the REQUEST.

    It runs before any response is started, so its failures become real HTTP
    status codes. Both cases are 404, not 403: a machine of another company,
    or a thread owned by someone else, must be indistinguishable from one that
    does not exist.
    """
    try:
        return await orchestrator.prepare_turn(user, payload)
    except MachineNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Machine '{payload.machine_id}' not found"
        )
    except ConversationNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Conversation '{payload.thread_id}' not found"
        )


# --- Chat endpoints

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    payload: ChatRequest, user: ChatUser, orchestrator: OrchestratorDep
) -> ChatResponse:
    """Non-streaming variant: the whole answer in one response. Handy for curl and tests."""
    context = await _prepare_turn(orchestrator, user, payload)
    return await orchestrator.handle(context, payload.query)


def _sse_format(event: dict) -> str:
    """
    Serializes one event dict into the SSE wire format:
        event: <type>
        data: <json>
        <blank line>
    The blank line terminates the event. json.dumps escapes newlines, so
    `data:` always stays on a single line as the format requires.
    ensure_ascii=False keeps accented characters (Italian) intact.
    """
    event_type = event.get("type", "message")
    data = json.dumps(event, ensure_ascii=False)
    return f"event: {event_type}\ndata: {data}\n\n"


@router.post("/chat/stream")
async def chat_stream_endpoint(
    payload: ChatRequest, user: ChatUser, orchestrator: OrchestratorDep
) -> StreamingResponse:
    """
    Streaming variant, as Server-Sent Events over POST.

    Two phases, and the split is the point:
      1. prepare the turn HERE, in the endpoint body: a failure is still an
         HTTP error (404/422), because no response has been started yet;
      2. run the graph INSIDE the generator. The generator only starts after
         the 200 and the headers have been sent, so from there on a failure
         can only be reported as an `error` event within the stream.

    Note for the client: the browser's native EventSource supports GET only,
    so this endpoint must be consumed with fetch() and a stream reader.
    """
    context = await _prepare_turn(orchestrator, user, payload)

    async def event_generator():
        async for event in orchestrator.handle_stream(context, payload.query):
            yield _sse_format(event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disables proxy buffering (nginx)
        },
    )


# --- History

@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    user: ChatUser,
    orchestrator: OrchestratorDep,
    machine_id: str | None = None,
) -> list[ConversationSummary]:
    """
    The caller's conversations, newest first. With ?machine_id=… only those
    about that machine. The user is taken from the session cookie, never from
    the request; guests get 403 like every other chat endpoint.
    """
    return await orchestrator.list_conversations(user, machine_id)

@router.get("/conversations/{thread_id}/messages", response_model=ConversationHistory)
async def get_conversation_history(
    thread_id: UUID, user: ChatUser, orchestrator: OrchestratorDep
) -> ConversationHistory:
    # get_history returns None both when the thread does not exist and when it
    # belongs to another user: the two cases are deliberately the same 404.
    history = await orchestrator.get_history(user, thread_id)
    if history is None:
        raise HTTPException(
            status_code=404, detail=f"Conversation '{thread_id}' not found"
        )
    return history
