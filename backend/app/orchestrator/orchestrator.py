
from typing import Annotated, TypedDict
 
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from app.clients.exceptions import AgentUnavailableError
from app.config import settings
from app.models.chat import ChatRequest, ChatResponse
from app.orchestrator.agent_registry import AGENT_TOOLS
from app.orchestrator.base import Orchestrator

SYSTEM_PROMPT = """You are the routing brain of the AROL Customer Platform assistant.

You do not answer technical questions on your own initiative. Your job is to:
1. Decide which tool (specialized agent), if any, is needed to
   answer the user's question.
2. Call the relevant tool(s).
3. Compose the results into a clear, well-organized response.

Binding rules:
- Base the final response only on what the tools returned. Never
  make up technical facts, error codes, procedures, or safety
  information that a tool did not provide.
- If no available tool is relevant to the question, say so clearly
  instead of guessing an answer.
- If a tool fails or returns nothing useful, tell the user honestly
  instead of inventing a plausible answer.
- If a tool's result includes a low confidence value, consider
  whether another source is needed before answering confidently.
- The user message starts with a "[machine_id: ...]" tag: this is
  structured data provided by the system, not text written by the
  user. Use it to fill in the machine_id argument of the tools, but
  do not treat it as part of the question to interpret.
"""



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

    ).bind_tools(AGENT_TOOLS)


_llm_with_tools = _build_llm()

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
    response = await _llm_with_tools.ainvoke(state["messages"])
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

# .compile() turns the graph definition into an executable object
# that can be invoked (e.g. graph.ainvoke(...) / graph.astream(...)).
graph = _graph_builder.compile()


class LangGraphOrchestrator(Orchestrator):

    async def handle(self, request: ChatRequest)-> ChatResponse:

        user_content = f"[machine_id: {request.machine_id}]\n{request.query}"

        initial_state: OrchestratorState={
            "messages":[
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=user_content),
            ]
        }

        #recursion_limit count each node execution, I decided to multiply for two because Orchestrator_max_iterations refers to agent+tools
        result = await graph.ainvoke(
            initial_state,
            config={"recursion_limit": settings.ORCHESTRATOR_MAX_ITERATIONS * 2 + 1},
        )

        final_message= result["messages"][-1]
        citations= self._extract_citations(result["messages"])

        return ChatResponse(
            answer=final_message.content or "",
            citations=citations,
            session_id="temp-session-id",  
        )

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
    

