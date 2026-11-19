import asyncio
import copy
import json
import unittest
from unittest.mock import Mock, patch

import httpx
from ollama import ResponseError

from core.config import settings
from core.llm_adapter import LLMResponse, ToolCall
from iot_agent.agent import IoTAgent
from main import app


class FakeLLM:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    async def complete(self, messages, tools=None):
        self.requests.append((copy.deepcopy(messages), tools))
        return next(self.responses)


def call(name, **arguments):
    return LLMResponse(tool_calls=[ToolCall(name=name, arguments=arguments)])


class AgentFailuresTest(unittest.IsolatedAsyncioTestCase):
    async def invoke(self, llm, handler, agent="iot"):
        original_client = httpx.AsyncClient

        def client_factory(**kwargs):
            return original_client(transport=httpx.MockTransport(handler), **kwargs)

        task = {"query": "Check the available records.", "machine_id": "MCH-0001"}
        if agent == "docs":
            task["company_id"] = "CMP-001"
        async with original_client(
            transport=httpx.ASGITransport(app=app), base_url="http://test",
        ) as client:
            with patch("main.adapter", llm), patch("httpx.AsyncClient", side_effect=client_factory):
                return await client.post(f"/agents/{agent}/search", json=task)

    def tool_results(self, llm):
        return [json.loads(m["content"]) for m in llm.requests[-1][0] if m["role"] == "tool"]

    async def test_invalid_arguments_are_corrected_before_contacting_backoffice(self):
        for invalid in ("Active", 42):
            with self.subTest(invalid=invalid):
                llm = FakeLLM([
                    call("search_alarms", status=invalid),
                    call("search_alarms", status="Open"),
                    LLMResponse(content="No open alarms found in the selected window."),
                ])
                requests = []

                def handler(request):
                    requests.append(request)
                    self.assertEqual(request.url.params["status"], "Open")
                    return httpx.Response(200, json={"results": [], "summary": {"matched_alarms": 0}})

                response = await self.invoke(llm, handler)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(requests), 1)
                self.assertEqual(self.tool_results(llm)[0]["error_type"], "invalid_arguments")
                self.assertEqual(len(response.json()["observations"]), 1)

    async def test_backoffice_422_can_be_corrected_in_the_next_iteration(self):
        llm = FakeLLM([
            call("search_alarms", from_timestamp="yesterday"),
            call("search_alarms", from_timestamp="2026-08-03"),
            LLMResponse(content="No alarms found for that date."),
        ])

        def handler(request):
            if request.url.params["from_timestamp"] == "yesterday":
                return httpx.Response(422, json={"detail": "private service details"})
            return httpx.Response(200, json={"results": []})

        response = await self.invoke(llm, handler)
        error = self.tool_results(llm)[0]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(error["error_type"], "invalid_arguments")
        self.assertEqual(error["http_status"], 422)
        self.assertNotIn("private service details", error["error"])

    async def test_service_failures_preserve_other_successful_tool_results(self):
        cases = [
            (503, "service_unavailable"), (429, "service_unavailable"),
            (403, "access_denied"), (404, "not_found"),
            (httpx.ConnectError, "service_unavailable"),
            (httpx.ReadTimeout, "timeout"),
            (httpx.RemoteProtocolError, "service_unavailable"),
        ]
        for failure, expected_type in cases:
            with self.subTest(failure=failure):
                llm = FakeLLM([
                    LLMResponse(tool_calls=[
                        ToolCall(name="search_alarms", arguments={}),
                        ToolCall(name="search_maintenance", arguments={}),
                    ]),
                    LLMResponse(content="Alarm lookup failed; there are no matching tickets."),
                ])

                def handler(request):
                    if request.url.path.endswith("/alarms"):
                        if isinstance(failure, int):
                            return httpx.Response(failure, text="private service details")
                        raise failure("private service details", request=request)
                    return httpx.Response(200, json={"results": [], "summary": {"matched_tickets": 0}})

                response = await self.invoke(llm, handler)
                self.assertEqual(response.status_code, 200)
                error, success = self.tool_results(llm)
                self.assertEqual(error["error_type"], expected_type)
                self.assertNotIn("private service details", error["error"])
                self.assertEqual(success["tool"], "search_maintenance")
                self.assertEqual([o["kind"] for o in response.json()["observations"]], ["maintenance"])

    async def test_docs_transport_failure_returns_no_fabricated_sources(self):
        llm = FakeLLM([call("search_orders"), LLMResponse(content="Orders could not be consulted.")])

        def handler(request):
            raise httpx.ConnectError("offline", request=request)

        response = await self.invoke(llm, handler, agent="docs")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sources"], [])
        self.assertEqual(response.json()["confidence"], 0.0)
        self.assertEqual(self.tool_results(llm)[0]["error_type"], "service_unavailable")

    async def test_manual_embedding_failure_returns_no_fabricated_citations(self):
        llm = FakeLLM([
            call("search_manual", query="maintenance"),
            LLMResponse(content="The manual search service is unavailable."),
        ])
        store = Mock()
        store.get_languages.return_value = ["EN"]
        store.query.side_effect = ResponseError("private model details", status_code=500)
        with patch("manuals_agent.agent.get_vector_store", return_value=store):
            response = await self.invoke(llm, Mock(), agent="manuals")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["citations"], [])
        self.assertEqual(self.tool_results(llm)[0]["error_type"], "service_unavailable")

    async def test_error_on_last_iteration_still_reaches_final_synthesis(self):
        llm = FakeLLM([call("unknown"), LLMResponse(content="The requested tool is not available.")])
        with patch.object(settings, "MAX_ITERATIONS", 1):
            response = await self.invoke(llm, Mock())
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(llm.requests[-1][1])
        self.assertEqual(self.tool_results(llm)[0]["error_type"], "unknown_tool")

    async def test_unexpected_errors_and_cancellation_are_not_swallowed(self):
        for error in (RuntimeError("programming error"), asyncio.CancelledError()):
            with self.subTest(error=type(error).__name__):
                llm = FakeLLM([call("search_alarms")])
                with patch.object(IoTAgent, "_execute_tool", side_effect=error):
                    with self.assertRaises(type(error)):
                        await self.invoke(llm, Mock())

    async def test_whole_run_deadline_covers_llm_and_tools(self):
        for stage in ("llm", "tool"):
            with self.subTest(stage=stage):
                cancelled = asyncio.Event()

                async def blocked(*args, **kwargs):
                    try:
                        await asyncio.Event().wait()
                    finally:
                        cancelled.set()

                llm = FakeLLM([call("search_alarms")])
                target = patch.object(llm, "complete", side_effect=blocked) if stage == "llm" else patch.object(
                    IoTAgent, "_execute_tool", side_effect=blocked,
                )
                with patch.object(settings, "AGENT_TIMEOUT_SECONDS", 0.02), target:
                    response = await self.invoke(llm, Mock())
                self.assertEqual(response.status_code, 504)
                self.assertIn("exceeded", response.json()["detail"])
                self.assertTrue(cancelled.is_set())


if __name__ == "__main__":
    unittest.main()
