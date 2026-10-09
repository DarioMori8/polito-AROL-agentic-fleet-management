import json
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, AsyncIterator, TypedDict
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_ollama import ChatOllama
from langfuse.langchain import CallbackHandler
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from app.config import settings
from sqlmodel import select


from app.db.models import PREVIEW_MAX_CHARS,Conversation, User
from app.models.chat import ChatRequest, ChatResponse, ConversationHistory, ConversationSummary, Denial, HistoryMessage, MessageRole
from app.orchestrator.agent_registry import AGENT_TOOLS
from app.orchestrator.base import (
    ConversationNotFoundError,
    MachineNotFoundError,
    Orchestrator,
    TurnContext,
)
from app.resources.repository import DbMachineRepository

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are the routing brain of the AROL Customer Platform assistant.

You do not answer technical questions on your own initiative. For every
user message you choose exactly one of four actions:

1. ROUTE — the message contains a concrete, searchable technical intent
   (a symptom, an error code, a named component, a specific procedure).
   Call the relevant tool(s), then compose their results into a clear,
   well-organized response.

2. CLARIFY — the message expresses a technical need but is too
   underspecified for any tool to help (e.g. "I have to fix this machine,
   can you help me?"). Do NOT call a tool and do NOT apologize. Ask the
   user 1-3 targeted questions to gather what a tool would need: observed
   symptoms, error codes shown on the display, what the machine was doing
   when the issue appeared. Keep the tone helpful and welcoming.

3. CHITCHAT — the message is a greeting, an introduction, thanks, or
   other conversational courtesy with no technical intent (e.g. "hi",
   "my name is Dario", "thanks!"). Do NOT call a tool and do NOT decline.
   Reply briefly and warmly, and steer the user toward what you can help
   with: the problem they are facing on their machine. Keep it to one or
   two sentences — you are opening a door to a technical conversation, not
   making small talk for its own sake.

4. DECLINE — the message has a real intent but no available tool is
   relevant to it even in principle (e.g. a request unrelated to AROL
   machines and their documentation). Say so politely, in one sentence,
   and redirect: state that you can help with the manuals and maintenance
   of their machines. Do not answer the off-topic request itself.

Asking a clarifying question (CLARIFY) or greeting the user (CHITCHAT) is
a routing action, not a technical answer: it is always allowed and never
counts as "answering on your own initiative." When in doubt between ROUTE
and CLARIFY, prefer CLARIFY — routing a vague request wastes a tool call
and produces a non-answer.

Binding rules:
- Always reply in the language the user wrote in, even though the tools
  and their results are in English: translate the tool content faithfully.
- Base any technical content in the final response only on what the tools
  returned. Never make up technical facts, error codes, procedures, or
  safety information that a tool did not provide. Every step, value, tool
  or component you mention must appear in a tool result. Never present text
  as a quotation from a manual unless it is in a tool result, and never cite
  a page number that is not among the returned citations.
- If the returned citations are about something else than the question
  (e.g. legal declarations, lubrication schemes, unrelated figures), treat
  the search as having found nothing: do not build an answer out of them.
- If a tool fails or returns nothing useful, tell the user honestly that
  the information was not found, and ask for more detail (e.g. the exact
  symptom or error code) so you can search again. Do NOT fill the gap with
  what a manual "usually" or "typically" contains, and do NOT list example
  maintenance tasks, components, or procedures from your own knowledge:
  if the tool did not return it, it does not go in the response. This is
  different from CLARIFY: here you already called a tool and it came back
  empty; there the request was too vague to call one at all.
- If a tool's result includes a low confidence value, consider whether
  another source is needed before answering confidently.
- Access control: the user may not be allowed to see every kind of data.
  Do NOT try to guess what the user can see: when a question needs a tool,
  call it; access is checked by the system. If a tool result contains
  "denied", tell the user clearly, in one or two sentences, that this
  information is outside their access profile. Do not try another tool to
  obtain the same information, do not answer it from general knowledge, and
  do not suggest it simply does not exist. If the question also had a part
  that was answered, answer that part normally.
- Every conversation is about one specific machine, already selected by
  the system: the tools are automatically scoped to it. Never ask the user
  which machine they mean. Knowing the machine does not tell you what is
  wrong with it, so a bare "help me fix it" still requires CLARIFY.
"""

_SYSTEM_MESSAGE = SystemMessage(content=SYSTEM_PROMPT)


class OrchestratorState(TypedDict):
    """
    The state of the graph. `add_messages` is a reducer: it tells LangGraph to
    APPEND the messages a node returns to the existing list, instead of
    replacing it.
    """
    messages: Annotated[list[BaseMessage], add_messages]


def _build_llm():
    # bind_tools sends the tool schemas to the model with every call.
    return ChatOllama(
        model=settings.ORCHESTRATOR_OLLAMA_MODEL,
        base_url=settings.ORCHESTRATOR_OLLAMA_BASE_URL,
        num_ctx=settings.ORCHESTRATOR_NUM_CTX,
        reasoning=True,
    ).bind_tools(AGENT_TOOLS)


_llm_with_tools = _build_llm()

# Reads its credentials from os.environ (see the bridge at the end of config.py).
_langfuse_handler = CallbackHandler()


async def _agent_node(state: OrchestratorState) -> dict:
    """
    The "agent" node: invokes the LLM with the whole conversation.

    The model can either return plain text (the turn is done) or one or more
    tool_calls. The returned dict is merged into the state by add_messages.
    The system message is prepended on every call and never stored, so a
    prompt change applies to old conversations too.
    """
    messages = [_SYSTEM_MESSAGE, *state["messages"]]
    response = await _llm_with_tools.ainvoke(messages)
    return {"messages": [response]}


# Executes every tool call in the last AI message (in parallel when several).
_tool_node = ToolNode(AGENT_TOOLS)

# ReAct loop: agent -> (tool_calls? tools -> agent) -> ... -> END
_graph_builder = StateGraph(OrchestratorState)
_graph_builder.add_node("agent", _agent_node)
_graph_builder.add_node("tools", _tool_node)
_graph_builder.add_edge(START, "agent")
# After "agent": tool_calls in the last message -> "tools", otherwise END.
_graph_builder.add_conditional_edges("agent", tools_condition)
# After the tools ran, always back to the model so it can read the results.
_graph_builder.add_edge("tools", "agent")


@asynccontextmanager
async def build_graph():
    """
    Owns the graph's lifetime: opens the durable SQLite checkpointer, compiles
    the graph with it, and yields the compiled graph for the duration of the
    `async with` block (the app lifespan). On exit the connection is closed.
    """
    Path(settings.CHECKPOINT_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(settings.CHECKPOINT_DB_PATH) as checkpointer:
        await checkpointer.setup()
        yield _graph_builder.compile(checkpointer=checkpointer)


# --- Artifact helpers

def normalize_artifact(artifact: dict) -> list[dict]:
    """
    Single source of truth for turning one tool artifact into a flat list of
    sources, each carrying a `kind` the frontend switches on. Manuals
    citations become kind="manual"; docs sources and iot observations already
    carry their own kind. An error artifact yields an empty list.
    """
    sources: list[dict] = []
    for citation in artifact.get("citations", []):
        sources.append({"kind": "manual", **citation})
    sources.extend(artifact.get("sources", []))
    sources.extend(artifact.get("observations", []))
    return _dedupe(sources)


def _dedupe(sources: list[dict]) -> list[dict]:
    """
    Drop exact duplicates, keeping the first occurrence and the original
    order. An agent with its own internal loop may return the same citation
    once per internal search: the client should see it once.

    The key is the JSON of the whole source (sort_keys makes it independent
    of key order), so it works for every kind without knowing its fields.
    """
    seen: set[str] = set()
    unique: list[dict] = []
    for source in sources:
        key = json.dumps(source, sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            unique.append(source)
    return unique


def _current_turn(messages: list[BaseMessage]) -> list[BaseMessage]:
    """
    With a checkpointer, the graph result holds the WHOLE thread, not just
    this turn. The current turn starts at the last HumanMessage.
    """
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            return messages[i:]
    return messages


def _denial_of(msg: BaseMessage) -> Denial | None:
    """The access denial carried by a tool result, if any."""
    if isinstance(msg, ToolMessage) and isinstance(msg.artifact, dict):
        denied = msg.artifact.get("denied")
        if isinstance(denied, dict):
            return Denial(tool=msg.name or "", **denied)
    return None


def _extract_denials(messages: list[BaseMessage]) -> list[Denial]:
    return [d for msg in messages if (d := _denial_of(msg)) is not None]


def _extract_sources(messages: list[BaseMessage]) -> list[dict]:
    sources: list[dict] = []
    for msg in messages:
        if isinstance(msg, ToolMessage) and isinstance(msg.artifact, dict):
            sources.extend(normalize_artifact(msg.artifact))
    return _dedupe(sources)

def _make_preview(query: str) -> str:
    """First line of the question, cut at PREVIEW_MAX_CHARS with an ellipsis."""
    text = " ".join(query.split())          # collapse newlines and runs of spaces
    if len(text) <= PREVIEW_MAX_CHARS:
        return text
    return text[: PREVIEW_MAX_CHARS - 1].rstrip() + "…"


def _project_messages(messages: list[BaseMessage]) -> list[HistoryMessage]:
    """
    Turn the raw graph messages into the human-visible conversation: user
    questions and final answers only, with each answer carrying the sources
    produced by the tools during its turn.
    """
    projected: list[HistoryMessage] = []
    # The "drawer": sources seen in this turn, waiting for the answer that
    # closes it.
    pending_sources: list[dict] = []
    pending_denied: list[Denial] = []

    for msg in messages:
        if isinstance(msg, HumanMessage):
            projected.append(HistoryMessage(role=MessageRole.USER, content=msg.content))

        elif isinstance(msg, ToolMessage):
            # Sources live in the tool artifact, not in the answer.
            if isinstance(msg.artifact, dict):
                pending_sources.extend(normalize_artifact(msg.artifact))
            if (denial := _denial_of(msg)) is not None:
                pending_denied.append(denial)

        elif isinstance(msg, AIMessage):
            # No text = the "decide to call a tool" step: mechanics, not
            # conversation.
            if not msg.content:
                continue
            projected.append(HistoryMessage(
                role=MessageRole.ASSISTANT,
                content=msg.content,
                sources=_dedupe(pending_sources),
                denied=pending_denied,
            ))
            pending_sources = []
            pending_denied = []

    return projected


# --- Orchestrator

class LangGraphOrchestrator(Orchestrator):

    def __init__(self, graph, session_factory):
        # Both are injected: the orchestrator knows nothing about app.state,
        # the lifespan or FastAPI, and has no circular import with main.py.
        # It receives a session FACTORY, not a session: it opens one only for
        # short checks and closes it before the graph runs, so no DB session
        # ever outlives the streaming generator.
        self._graph = graph
        self._session_factory = session_factory

    # --- Phase 1: validation

    async def prepare_turn(self, user: User, request: ChatRequest) -> TurnContext:
        """
        The tenant comes from the authenticated user, never from the request.
        The request only NAMES a machine; here we check that the machine
        belongs to the user's company and that the thread (if any) belongs to
        the user and to that machine.
        """
        async with self._session_factory() as db:
            machine = await DbMachineRepository(db, user.company_id).get(request.machine_id)
            if machine is None:
                raise MachineNotFoundError(request.machine_id)

            if request.thread_id is None:
                thread_id = uuid.uuid4()
                db.add(Conversation(
                    thread_id=str(thread_id),
                    user_id=user.id,
                    machine_id=machine.id,
                    preview=_make_preview(request.query),

                ))
                await db.commit()
                is_new = True
            else:
                conversation = await db.get(Conversation, str(request.thread_id))
                if (
                    conversation is None
                    or conversation.user_id != user.id
                    or conversation.machine_id != machine.id
                ):
                    raise ConversationNotFoundError(request.thread_id)
                thread_id = request.thread_id
                is_new = False

        return TurnContext(
            thread_id=thread_id,
            user_id=user.id,
            company_id=user.company_id,
            machine_id=machine.id,
            visibility=user.visibility,
            is_new=is_new,
        )

    def _run_config(self, context: TurnContext) -> dict:
        return {
            # Each agent->tools round trip executes two nodes.
            "recursion_limit": settings.ORCHESTRATOR_MAX_ITERATIONS * 2 + 1,
            "callbacks": [_langfuse_handler],
            # thread_id selects the checkpoint; company_id, machine_id and
            # visibility are read by the tools and never exposed to the model.
            "configurable": {
                "thread_id": str(context.thread_id),
                "company_id": context.company_id,
                "machine_id": context.machine_id,
                "visibility": context.visibility.value,
            },
            # Groups traces by user and conversation in Langfuse.
            "metadata": {
                "langfuse_user_id": context.user_id,
                "langfuse_session_id": str(context.thread_id),
            },
        }

    # --- Phase 2: execution

    async def handle(self, context: TurnContext, query: str) -> ChatResponse:
        result = await self._graph.ainvoke(
            {"messages": [HumanMessage(content=query)]},
            config=self._run_config(context),
        )
        messages = result["messages"]
        turn = _current_turn(messages)
        return ChatResponse(
            answer=messages[-1].content or "",
            sources=_extract_sources(turn),
            denied=_extract_denials(turn),
            thread_id=context.thread_id,
        )

    async def handle_stream(self, context: TurnContext, query: str) -> AsyncIterator[dict]:
        """
        Streaming variant of handle(). Yields semantic events as the graph
        runs: start / thinking / token / status / denied / error / sources / done.
        Serializing them into SSE is the endpoint's job: this method stays
        transport-agnostic.
        """
        # First, so the client has the thread id before any token arrives.
        yield {"type": "start", "thread_id": str(context.thread_id), "is_new": context.is_new}

        sources: list[dict] = []

        try:
            async for stream_mode, payload in self._graph.astream(
                {"messages": [HumanMessage(content=query)]},
                config=self._run_config(context),
                stream_mode=["messages", "updates"],
            ):
                # --- LLM output chunks, only from the "agent" node
                if stream_mode == "messages":
                    chunk, metadata = payload
                    if metadata.get("langgraph_node") != "agent":
                        continue

                    reasoning = chunk.additional_kwargs.get("reasoning_content")
                    if reasoning:
                        yield {"type": "thinking", "text": reasoning}
                    if chunk.content:
                        yield {"type": "token", "text": chunk.content}

                # --- Node completions: tool calls, tool results
                elif stream_mode == "updates":
                    for _node_name, node_update in payload.items():
                        if not isinstance(node_update, dict):
                            continue
                        # With parallel tool calls the "tools" update holds
                        # several ToolMessages: every one must be read.
                        for msg in node_update.get("messages", []):
                            # The model decided to call a tool: announce it,
                            # so the silent HTTP call does not look like a freeze.
                            for tc in getattr(msg, "tool_calls", None) or []:
                                yield {
                                    "type": "status",
                                    "tool": tc["name"],
                                    "message": f"Consulting {tc['name']}...",
                                }
                            # A tool finished: read its structured artifact.
                            # An access denial: emitted by code, so the
                            # client learns about it deterministically.
                            if (denial := _denial_of(msg)) is not None:
                                yield {"type": "denied", **denial.model_dump()}
                            if isinstance(msg, ToolMessage) and isinstance(msg.artifact, dict):
                                if "error" in msg.artifact:
                                    yield {
                                        "type": "error",
                                        "recoverable": True,
                                        "message": msg.artifact["error"],
                                    }
                                sources.extend(normalize_artifact(msg.artifact))

            yield {"type": "sources", "sources": _dedupe(sources)}
            yield {"type": "done", "thread_id": str(context.thread_id)}

        except Exception:
            # The 200 is already sent: a fatal failure can only become an
            # event. The details go to the log; the client gets a generic
            # message, never internals such as URLs or stack traces.
            logger.exception("Graph run failed for thread %s", context.thread_id)
            yield {
                "type": "error",
                "recoverable": False,
                "message": "An internal error occurred while generating the answer.",
            }
            yield {"type": "done", "thread_id": str(context.thread_id)}

    # --- History

    async def get_history(self, user: User, thread_id: UUID) -> ConversationHistory | None:
        """
        None for an unknown thread AND for another user's thread: the caller
        must not be able to tell the two apart.
        """
        async with self._session_factory() as db:
            conversation = await db.get(Conversation, str(thread_id))
        if conversation is None or conversation.user_id != user.id:
            return None

        snapshot = await self._graph.aget_state(
            {"configurable": {"thread_id": str(thread_id)}}
        )
        # A thread whose first turn failed has a Conversation row but no
        # checkpoint: it is an existing, empty conversation, not a 404.
        messages = (snapshot.values or {}).get("messages", [])

        return ConversationHistory(
            thread_id=thread_id,
            machine_id=conversation.machine_id,
            messages=_project_messages(messages),
        )

    async def list_conversations(
        self, user: User, machine_id: str | None = None
    ) -> list[ConversationSummary]:
        """
        The caller's own conversations, newest first, optionally only those
        about one machine.

        Ownership is the filter itself (user_id), so another user's threads
        can never appear. A machine_id that is not the caller's (another
        company's, or nonexistent) simply matches nothing: the answer is an
        empty list, indistinguishable from "no conversations yet".
        """
        query = select(Conversation).where(Conversation.user_id == user.id)
        if machine_id is not None:
            query = query.where(Conversation.machine_id == machine_id)
        query = query.order_by(Conversation.created_at.desc())

        async with self._session_factory() as db:
            rows = (await db.exec(query)).all()

        return [
            ConversationSummary(
                thread_id=UUID(row.thread_id),
                preview=row.preview,
                created_at=row.created_at,
            )
            for row in rows
        ]
