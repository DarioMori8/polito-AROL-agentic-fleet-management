from core.base_agent import BaseAgent
from core.llm_adapter import ToolCall, LLMResponse
from core.schemas import SearchManualTask, SearchManualResponse, Citation
from core.vectorstore import get_vector_store
from manuals_agent.prompts import SYSTEM_PROMPT
from manuals_agent.tools import TOOLS


class ManualsAgent(BaseAgent):
    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    @property
    def tools(self) -> list[dict]:
        return TOOLS

    async def run(self, task: SearchManualTask) -> SearchManualResponse:
        self._task = task
        return await super().run(task)

    def _user_message(self, task: SearchManualTask) -> str:
        return task.query

    async def _execute_tool(self, tool_call: ToolCall) -> dict:
        if tool_call.name != "search_manual":
            return {"error": f"unknown tool: {tool_call.name}"}

        query = tool_call.arguments.get("query", self._task.query)
        results = get_vector_store().query(
            text=query,
            k=5,
            where={"machine_id": self._task.machine_id},
        )
        return {"results": results}

    def _build_response(self, final: LLMResponse, tool_results: list[dict]) -> SearchManualResponse:
        citations = [
            Citation(doc=chunk["doc"], page=chunk["page"], snippet=chunk["text"][:300])
            for result in tool_results
            for chunk in result.get("results", [])
        ]
        return SearchManualResponse(
            answer=final.content or "",
            citations=citations,
            confidence=1.0 if citations else 0.0,
        )

