from core.base_agent import BaseAgent
from core.llm_adapter import ToolCall, LLMResponse
from contracts import SearchManualTask, SearchManualResponse, Citation
from manuals_agent.prompts import SYSTEM_PROMPT
from manuals_agent.tools import TOOLS

class ManualsAgent(BaseAgent):
    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    @property
    def tools(self) -> list[dict]:
        return TOOLS

    def _user_message(self, task: SearchManualTask) -> str:
        return task.query

    async def _execute_tool(self, tool_call: ToolCall) -> dict:
        return {}

    def _build_response(self, final: LLMResponse, tool_results: list[dict]) -> SearchManualResponse:
        return SearchManualResponse(
            answer=final.content,
            citations=[Citation(doc="manual_1.pdf", page=12, snippet="this is a good citation")],
            confidence=0.9
        ) 
        
