from abc import ABC, abstractmethod

import httpx
from pydantic import BaseModel

from app.config import settings


class ToolCall(BaseModel):
    name: str
    arguments: dict


class LLMResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] = []


class LLMAdapter(ABC):
    @abstractmethod
    async def complete(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> LLMResponse:
        ...


class OllamaAdapter(LLMAdapter):
    def __init__(self):
        self.base_url = settings.ORCHESTRATOR_OLLAMA_BASE_URL
        self.model = settings.ORCHESTRATOR_OLLAMA_MODEL

    async def complete(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        payload = {"model": self.model, "messages": messages, "stream": False}
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=100) as client:
            r = await client.post(f"{self.base_url}/api/chat", json=payload)
            r.raise_for_status()

        message = r.json()["message"]
        tool_calls = [
            ToolCall(name=tc["function"]["name"], arguments=tc["function"]["arguments"])
            for tc in message.get("tool_calls", [])
        ]
        return LLMResponse(content=message.get("content"), tool_calls=tool_calls)


def get_orchestrator_llm() -> LLMAdapter:
    if settings.ORCHESTRATOR_LLM_PROVIDER == "ollama":
        return OllamaAdapter()
    raise ValueError(
        f"Orchestrator LLM provider not supported: {settings.ORCHESTRATOR_LLM_PROVIDER}"
    )