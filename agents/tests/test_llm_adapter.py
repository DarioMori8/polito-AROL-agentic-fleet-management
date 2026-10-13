import asyncio
import unittest
from unittest.mock import patch

import httpx

from core.config import settings
from core.llm_adapter import OllamaAdapter


class OllamaAdapterTest(unittest.TestCase):
    def test_preserves_thinking_and_tool_calls_with_explicit_context(self):
        import json
        def handler(request):
            payload = json.loads(request.content)
            self.assertEqual(payload["options"]["num_ctx"], settings.OLLAMA_NUM_CTX)
            return httpx.Response(200, json={"message": {
                "content": "", "thinking": "Find the relevant section.",
                "tool_calls": [{"function": {"name": "search_manual", "arguments": {"query": "maintenance"}}}],
            }})
        client_class = httpx.AsyncClient
        def factory(**kwargs):
            return client_class(transport=httpx.MockTransport(handler), **kwargs)
        with patch("core.llm_adapter.httpx.AsyncClient", side_effect=factory):
            result = asyncio.run(OllamaAdapter().complete([{"role": "user", "content": "maintenance"}]))
        self.assertEqual(result.thinking, "Find the relevant section.")
        self.assertEqual(result.tool_calls[0].name, "search_manual")
        self.assertEqual(result.content, "")
