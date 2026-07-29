from core.base_agent import BaseAgent
from core.llm_adapter import ToolCall, LLMResponse
from core.docs_client import get_docs_client
from contracts import (
    SearchDocsTask,
    SearchDocsResponse,
    Source,
    DocumentSource,
    OrderSource,
    QuoteSource,
)
from docs_agent.prompts import SYSTEM_PROMPT
from docs_agent.tools import TOOLS

# Maps each tool to the source variant its results parse into, so heterogeneous
# tool results can be turned back into typed sources.
SOURCE_BY_TOOL = {
    "search_documents": DocumentSource,
    "search_orders": OrderSource,
    "search_quotes": QuoteSource,
}


class DocsAgent(BaseAgent):
    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    @property
    def tools(self) -> list[dict]:
        return TOOLS

    async def run(self, task: SearchDocsTask) -> SearchDocsResponse:
        self._task = task
        return await super().run(task)

    def _user_message(self, task: SearchDocsTask) -> str:
        return task.query

    async def _execute_tool(self, tool_call: ToolCall) -> dict:
        args = tool_call.arguments
        client = get_docs_client()
        # machine_id always comes from the authenticated task, never from the tool
        # call, so the LLM cannot reach another customer's machine.
        machine_id = self._task.machine_id

        if tool_call.name == "search_documents":
            results = await client.search_documents(
                query=args.get("query", self._task.query),
                document_type=args.get("document_type"),
                order_id=args.get("order_id"),
                machine_id=machine_id,
            )
        elif tool_call.name == "search_orders":
            results = await client.search_orders(
                order_id=args.get("order_id"),
                status=args.get("status"),
                order_type=args.get("order_type"),
                machine_id=machine_id,
            )
        elif tool_call.name == "search_quotes":
            results = await client.search_quotes(
                quote_id=args.get("quote_id"),
                status=args.get("status"),
                machine_id=machine_id,
            )
        else:
            return {"error": f"unknown tool: {tool_call.name}"}

        return {"tool": tool_call.name, "results": results}

    def _build_response(self, final: LLMResponse, tool_results: list[dict]) -> SearchDocsResponse:
        sources: list[Source] = []
        for result in tool_results:
            source_model = SOURCE_BY_TOOL.get(result.get("tool"))
            if source_model is None:
                continue
            sources.extend(source_model(**row) for row in result.get("results", []))

        return SearchDocsResponse(
            answer=final.content or "",
            sources=sources,
            confidence=1.0 if sources else 0.0,
        )
