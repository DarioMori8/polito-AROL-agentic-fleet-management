
from typing import Annotated, TypedDict, AsyncIterator
import uuid
 
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage, AIMessage
from langfuse.langchain import CallbackHandler
from langchain_ollama import ChatOllama
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from contextlib import asynccontextmanager
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from contracts import Citation
from app.models.chat import ChatRequest, ChatResponse, ConversationHistory, HistoryMessage, MessageRole

from app.config import settings
from app.orchestrator.agent_registry import AGENT_TOOLS
from app.orchestrator.base import Orchestrator
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
   with: which machine they are working on and what problem they are
   facing. Keep it to one or two sentences — you are opening a door to a
   technical conversation, not making small talk for its own sake.

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
- Base any technical content in the final response only on what the tools
  returned. Never make up technical facts, error codes, procedures, or
  safety information that a tool did not provide.
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
- The user message starts with a "[machine_id: ...]" tag: this is
  structured data provided by the system, not text written by the user.
  Use it to fill in the machine_id argument of the tools, but do not treat
  it as part of the question to interpret. Note that a machine_id alone is
  not a searchable intent — knowing which machine does not tell you what is
  wrong with it, so a bare "help me fix it" still requires CLARIFY.
"""

_SYSTEM_MESSAGE = SystemMessage(content=SYSTEM_PROMPT)

class OrchestratorState(TypedDict):
    """
    The Status of graph. 'add_messages' is a 'reducer': it says to LandGraph to add the new messages,
    which comes from a node,at existing list.
    """
    messages: Annotated[list[BaseMessage], add_messages]



def _build_llm()->ChatOllama:
    #Generate the tools schema to send to model

    return ChatOllama(
        model=settings.ORCHESTRATOR_OLLAMA_MODEL,
        base_url= settings.ORCHESTRATOR_OLLAMA_BASE_URL,
        num_ctx=settings.ORCHESTRATOR_NUM_CTX,
        reasoning=True,
    ).bind_tools(AGENT_TOOLS)


_llm_with_tools = _build_llm()


_langfuse_handler = CallbackHandler()


async def _agent_node(state: OrchestratorState) -> dict:
    """
    The "agent" node in the LangGraph graph: invokes the LLM with the
    current conversation history.

    The LLM was already bound to the available tools via `.bind_tools()`
    in `_build_llm()`, so on each call it can either:
      - return a plain text response (conversation is done), or
      - return one or more tool_calls, if it decides an agent/tool
        needs to be invoked to answer the user.

    The returned dict is merged into the graph state by the `add_messages`
    reducer defined above, which appends the new AI message to
    `state["messages"]` instead of overwriting the whole history.
    """
    messages = [_SYSTEM_MESSAGE, *state["messages"]]
    response = await _llm_with_tools.ainvoke(messages)
    return {"messages": [response]}


#Search and execute automatically the tool requested in the last message by LLM
_tool_node = ToolNode(AGENT_TOOLS)



# Build the state graph, using OrchestratorState as the shared state
# structure that flows through every node.
_graph_builder = StateGraph(OrchestratorState)

# Register the two nodes of the graph:
# - "agent": calls the LLM (see _agent_node)
# - "tools": executes whichever tool(s) the LLM decided to call (see _tool_node)
_graph_builder.add_node("agent", _agent_node)
_graph_builder.add_node("tools", _tool_node)

# Entry point: every run of the graph starts at the "agent" node.
_graph_builder.add_edge(START, "agent")

# Conditional edge: after "agent" runs, check the last message.
# If it contains tool_calls -> go to "tools".
# Otherwise -> go to END (conversation turn is complete).
# This replaces the manual check:
#     if not response.tool_calls: return self._build_response(...)
_graph_builder.add_conditional_edges("agent", tools_condition)

# After the tool(s) have been executed, always loop back to "agent"
# so the LLM can reason again with the new tool result in context.
# This is the core loop of the ReAct pattern (Reason -> Act -> Reason -> ...).
_graph_builder.add_edge("tools", "agent")

@asynccontextmanager
async def build_graph():
    """
    Async context manager that owns the graph's construction: it opens a
    durable SQLite checkpointer, compiles the graph with it, and yields
    the compiled graph for the lifetime of the `async with` block that
    uses it. When that block exits (app shutdown), the SQLite connection
    is closed cleanly by the inner `async with` below.
    """
    async with AsyncSqliteSaver.from_conn_string(settings.CHECKPOINT_DB_PATH) as checkpointer:
        await checkpointer.setup()
        graph = _graph_builder.compile(checkpointer=checkpointer)
        yield graph

class LangGraphOrchestrator(Orchestrator):

    def __init__(self, graph):
        # The graph is injected, not fetched: the orchestrator operates on
        # the graph it's given and knows nothing about where it came from
        # (app.state, lifespan, FastAPI). This keeps it free of any web-app
        # dependency and avoids a circular import with main.py.
        self._graph = graph

    async def handle(self, request: ChatRequest)-> ChatResponse:

        session_id = request.session_id or str(uuid.uuid4())


        user_content = f"[machine_id: {request.machine_id}]\n{request.query}"

        initial_state: OrchestratorState={
            "messages":[HumanMessage(content=user_content)]
        }

        #recursion_limit count each node execution, I decided to multiply for two because Orchestrator_max_iterations refers to agent+tools
        result = await self._graph.ainvoke(
            initial_state,
            config={
                "recursion_limit": settings.ORCHESTRATOR_MAX_ITERATIONS * 2 + 1,
                "callbacks": [_langfuse_handler],
                "configurable": {"thread_id": session_id}
            },
        )

        final_message= result["messages"][-1]
        citations= self._extract_citations(result["messages"])

        return ChatResponse(
            answer=final_message.content or "",
            citations=citations,
            session_id=session_id,  
        )

    async def handle_stream(self, request: ChatRequest)-> AsyncIterator[dict]:
        """
            Streaming variant of handle(). Instead of returning a single
            ChatResponse, it yields a sequence of semantic events (dicts) as the
            graph executes: start / thinking / token / status / error / citations
            / done. The endpoint layer is responsible for serializing these into
            the SSE wire format — this method stays transport-agnostic.
        """
        session_id = request.session_id or str(uuid.uuid4())  

        user_content= f"[machine_id: {request.machine_id}]\n{request.query}"

        initial_state: OrchestratorState ={
                "messages": [HumanMessage(content=user_content)]

        }
        # Sent first so the frontend has the session id from the very start.
        # This is also the future thread_id once checkpointing is wired.
        yield {"type": "start", "session_id": session_id}

        citations: list[dict]= []

        try:
            async for stream_mode, payload in self._graph.astream(
                initial_state, 
                config={
                    "recursion_limit": settings.ORCHESTRATOR_MAX_ITERATIONS*2+1,
                    "callbacks": [_langfuse_handler],
                    "configurable": {"thread_id": session_id},
                },
                stream_mode=["messages", "updates"],
            ):
                # --- token / thinking: LLM output, only from the "agent" node ---
                if stream_mode == "messages":
                    chunk, metadata = payload
                    if metadata.get("langgraph_node") != "agent":
                        continue

                    reasoning= chunk.additional_kwargs.get("reasoning_content") #additional_kwarg is a dict and get is necessery to avoid KeyError
                    if(reasoning):
                        yield {"type": "thinking", "text": reasoning}

                    if (chunk.content):
                        yield {"type": "token", "text": chunk.content}

                # --- status / citations / recoverable errors: node completions ---
                elif stream_mode == "updates":
                    for _node_name, node_update in payload.items():
                        if not isinstance(node_update, dict):
                            continue
                        for msg in node_update.get("messages", []):
                        # The agent decided to call a tool -> announce it,
                        # so the silent HTTP call to the agent isn't a freeze.
                            for tc in getattr(msg, "tool_calls", None) or  []:
                                yield {
                                    "type": "status",
                                    "tool": tc["name"],
                                    "message": f"Consulting {tc['name']}...",
                                }
                             # A tool finished -> read its structured artifact.
                        if isinstance(msg, ToolMessage) and isinstance(msg.artifact, dict):
                            if "error" in msg.artifact:
                                yield {
                                    "type": "error",
                                    "recoverable": True,
                                    "message": msg.artifact["error"],
                                }
                            for c in msg.artifact.get("citations", []):
                                citations.append(c)

            yield {"type": "citations", "citations": citations}
            yield {"type": "done", "session_id": session_id}

        except Exception as exc:
            # Once streaming has begun we're already committed to HTTP 200,
            # so a fatal failure can't become a 500 — it becomes an event.
            yield {"type": "error", "recoverable": False, "message": str(exc)}
            yield {"type": "done", "session_id": session_id}



    def _project_messages(self, messages: list[BaseMessage]) -> list[HistoryMessage]:
        projected: list[HistoryMessage] = []
        pending_citations: list[Citation] = []   # the "drawer": citations seen in this turn,
                                                    # waiting to be attached to the answer that closes it

        for msg in messages:
            if isinstance(msg, HumanMessage):
                content = msg.content
          
                if content.startswith("[machine_id:") and "\n" in content:
                    content = content.split("\n", 1)[1]
                projected.append(HistoryMessage(
                    role=MessageRole.USER,
                    content=content,
                    citations=[],
                ))

            elif isinstance(msg, ToolMessage):
                # Citations live in the tool artifact, not in the answer.
                # Stash them; they belong to the assistant message that comes next.
                if isinstance(msg.artifact, dict):
                    for c in msg.artifact.get("citations", []):
                        pending_citations.append(Citation(**c))

            elif isinstance(msg, AIMessage):
                # An AIMessage with no text content is the "decide to call a tool" step:
                # pure mechanics, not part of the human-visible conversation. Skip it.
                if not msg.content:
                    continue
                # An AIMessage with text is the turn's final answer: attach the drawer,
                # then empty it for the next turn.
                projected.append(HistoryMessage(
                    role=MessageRole.ASSISTANT,
                    content=msg.content,
                    citations=pending_citations,
                ))
                pending_citations = []

        return projected

    
    async def get_history(self, session_id: str) -> ConversationHistory | None:
        config = {"configurable": {"thread_id": session_id}}
        snapshot = await self._graph.aget_state(config)

        # aget_state on an unknown thread returns an empty snapshot (no messages),
        # not an error. That's how we detect "conversation does not exist".
        messages = snapshot.values.get("messages", [])
        if not messages:
            return None

        projected = self._project_messages(messages)
        return ConversationHistory(session_id=session_id, messages=projected)




    def _extract_citations(self, messages: list[BaseMessage]) -> list[dict]:
        """
        Walks through the final message history looking for ToolMessage
        instances (the results produced by tools executed during the graph
        run) and extracts their citations, if any.
        """
        citations: list[dict] = []
        for msg in messages:
            if isinstance(msg, ToolMessage) and isinstance(msg.artifact, dict):
                tool_citations = msg.artifact.get("citations")
                if tool_citations:
                    citations.extend(tool_citations)
        return citations        
    

