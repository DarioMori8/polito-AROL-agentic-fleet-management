import json
from abc import ABC, abstractmethod

from core.config import settings
from core.llm_adapter import LLMAdapter, LLMResponse, ToolCall, get_llm_adapter
from core.observability import get_langfuse


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
        with get_langfuse().start_as_current_observation(
            name=type(self).__name__, as_type="agent", input=task.model_dump(),
            metadata={"machine_id": task.machine_id},
        ) as observation:
            response = await self._run(task)
            observation.update(output=response.model_dump())
            return response

    def _finish(self, final: LLMResponse, tool_results: list[dict]):
        with get_langfuse().start_as_current_observation(
            name="build_response", as_type="span",
        ) as observation:
            response = self._build_response(final, tool_results)
            observation.update(output=response.model_dump())
            return response

    async def _run(self, task):
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self._user_message(task)},
        ]
        tool_results: list[dict] = []

        for iteration in range(1, settings.MAX_ITERATIONS + 1):
            with get_langfuse().start_as_current_observation(
                name="agent.iteration", as_type="chain",
                metadata={"iteration": iteration},
            ):
                response = await self.llm.complete(messages, self.tools)

                if not response.tool_calls:
                    return self._finish(response, tool_results)

                messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                    "thinking": response.thinking or "",
                    "tool_calls": [
                        {"type": "function", "function": call.model_dump()}
                        for call in response.tool_calls
                    ],
                })
                for call in response.tool_calls:
                    with get_langfuse().start_as_current_observation(
                        name=call.name, as_type="tool", input=call.arguments,
                    ) as tool_observation:
                        result = await self._execute_tool(call)
                        tool_observation.update(output=result)
                        if "error" in result:
                            tool_observation.update(
                                level="ERROR", status_message=str(result["error"]),
                            )
                    tool_results.append(result)
                    messages.append(
                        {"role": "tool", "tool_name": call.name,
                         "content": json.dumps(result, ensure_ascii=False)}
                    )

        # Reserve a final synthesis after the tool budget, instead of reporting
        # success with an empty answer and a list of retrieved passages.
        messages.append({
            "role": "user",
            "content": (
                "Answer the original question now using only the tool results. "
                "Do not request more tools. If they do not answer the question, "
                "explain what is missing. Original question: " + self._user_message(task)
            ),
        })
        with get_langfuse().start_as_current_observation(
            name="agent.final_synthesis", as_type="chain",
            metadata={"iteration": settings.MAX_ITERATIONS + 1, "tool_budget_exhausted": True},
        ):
            final = await self.llm.complete(messages, None)
            return self._finish(final, tool_results)
