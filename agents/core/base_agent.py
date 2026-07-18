from abc import ABC, abstractmethod

from core.config import settings
from core.llm_adapter import LLMAdapter, LLMResponse, ToolCall, get_llm_adapter


class BaseAgent(ABC):
    def __init__(self, llm: LLMAdapter | None = None):
        self.llm = llm or get_llm_adapter()

    @property
    @abstractmethod
    def system_prompt(self) -> str: ...

    @property
    @abstractmethod
    def tools(self) -> list[dict]: ...

    @abstractmethod
    def _user_message(self, task) -> str: ...

    @abstractmethod
    async def _execute_tool(self, tool_call: ToolCall) -> dict: ...

    @abstractmethod
    def _build_response(self, final: LLMResponse, tool_results: list[dict]): ...

    async def run(self, task):
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self._user_message(task)},
        ]
        tool_results: list[dict] = []

        for _ in range(settings.MAX_ITERATIONS):
            response = await self.llm.complete(messages, self.tools)

            if not response.tool_calls:
                return self._build_response(response, tool_results)

            messages.append({"role": "assistant", "content": response.content or ""})
            for call in response.tool_calls:
                result = await self._execute_tool(call)
                tool_results.append(result)
                messages.append(
                    {"role": "tool", "name": call.name, "content": str(result)}
                )

        return self._build_response(LLMResponse(content=""), tool_results)
