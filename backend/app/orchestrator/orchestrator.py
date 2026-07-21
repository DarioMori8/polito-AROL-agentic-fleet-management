
import logging

from app.clients.exceptions import AgentUnavailableError
from app.config import settings
from app.models.chat import ChatRequest, ChatResponse
from app.orchestrator.agent_registry import as_llm_tool_defs, get_tool_by_name
from app.orchestrator.base import Orchestrator
from app.orchestrator.llm_adapter import LLMAdapter, ToolCall

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

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
"""


class LLMOrchestrator(Orchestrator):
    def __init__(self, llm: LLMAdapter, max_iterations: int | None = None):
        self.llm = llm
        self.max_iterations = max_iterations or settings.ORCHESTRATOR_MAX_ITERATIONS

    async def handle(self, request: ChatRequest) -> ChatResponse:
        logger.info(
            "New request: query=%r machine_id=%r",
            request.query,
            request.machine_id,
        )
        messages = self._build_messages(request)
        citations: list[dict] = []

        for iteration in range(1, self.max_iterations+1):
            logger.info("Iteration %s/%s — LLM call...", iteration, self.max_iterations)
            response = await self.llm.complete(messages, as_llm_tool_defs())

            if not response.tool_calls:
                logger.info(
                    "LLM has responded to the final answer (without tool): %r",
                    response.content,
                )
                return ChatResponse(
                    answer=response.content or "",
                    citations=citations,
                    session_id="temp-session-id", 
                )
            logger.info(
                "LLM has requested %s tool call(s): %s",
                len(response.tool_calls),
                [c.name for c in response.tool_calls],
            )

            messages.append({"role": "assistant", "content": response.content or ""})

            for call in response.tool_calls:
                logger.info("Execution tool '%s' with arguments: %s", call.name, call.arguments)
                result = await self._execute_tool(call)
                logger.info("Result tool '%s': %s", call.name, result)
                if isinstance(result, dict) and result.get("citations"):
                    citations.extend(result["citations"])
                messages.append(
                    {"role": "tool", "name": call.name, "content": str(result)}
                )

        logger.warning(
            "Orchestrator has finished  max_iterations=%s without a final answer",
            self.max_iterations,
        )
        return ChatResponse(
            answer="I couldn't complete this request. Could you rephrase it?",
            citations=citations,
            session_id="temp-session-id",
        )

    async def _execute_tool(self, call: ToolCall) -> dict:
        tool = get_tool_by_name(call.name)
        if tool is None:
            logger.error("The LLM requested an unknown tool: %s", call.name)
            return {"error": f"Tool unknown: {call.name}"}

        try:
            return await tool.handler(call.arguments)
        except AgentUnavailableError as exc:
            logger.warning("Agent for tool '%s' not available: %s", call.name, exc)
            return {"error": f"The service behind '{call.name}' is currently unavailable."}
        except KeyError as exc:
            logger.error("Missing arguments for tool '%s': %s", call.name, exc)
            return {"error": f"Missing arguments for tool '{call.name}': {exc}"}

    def _build_messages(self, request: ChatRequest) -> list[dict]:
        # Nessuna conversation_history per ora: ChatRequest ha solo
        # query e machine_id (niente persistenza sessione).
        # Quando arriverà, andrà messa qui, tra system e user.

        user_content = f"[machine_id: {request.machine_id}]\n{request.query}"
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]