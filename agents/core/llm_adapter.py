from abc import ABC, abstractmethod

import httpx
from pydantic import BaseModel

from core.config import settings


class ToolCall(BaseModel):
    name: str
    arguments: dict


class LLMResponse(BaseModel):
    content: str | None = None
    thinking: str | None = None
    tool_calls: list[ToolCall] = []


class LLMAdapter(ABC):
    @abstractmethod
    async def complete(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> LLMResponse:
        ...


class OllamaAdapter(LLMAdapter):
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL

    async def complete(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> LLMResponse:
        payload = {
            "model": self.model, "messages": messages, "stream": False,
            "options": {"num_ctx": settings.OLLAMA_NUM_CTX},
        }
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
        return LLMResponse(
            content=message.get("content"), thinking=message.get("thinking"),
            tool_calls=tool_calls,
        )


def get_llm_adapter() -> LLMAdapter:
    if settings.LLM_PROVIDER == "ollama":
        return OllamaAdapter()
    raise ValueError(f"Provider Not Supported: {settings.LLM_PROVIDER}")
