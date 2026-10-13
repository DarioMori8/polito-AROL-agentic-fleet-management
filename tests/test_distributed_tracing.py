"""Real SDK/LangGraph/ASGI integration; only Ollama and backoffice are simulated.

Run from the repository root with both services installed:
PYTHONPATH=backend:agents python -m unittest discover -s tests -v
"""

import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

# Never export test prompts to the user's project or contact a live LLM.
os.environ.update({
    "LANGFUSE_PUBLIC_KEY": "pk-lf-distributed-test",
    "LANGFUSE_SECRET_KEY": "sk-lf-distributed-test",
    "LANGFUSE_TRACING_ENABLED": "true",
    "OLLAMA_MODEL": "test-model",
    "ORCHESTRATOR_OLLAMA_MODEL": "test-model",
})

import httpx
from langfuse import Langfuse
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from ollama import ResponseError
from langchain_core.runnables import RunnableLambda
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from tenacity import wait_none

EXPORTER = InMemorySpanExporter()
LANGFUSE = Langfuse(
    tracer_provider=TracerProvider(), span_exporter=EXPORTER,
)

from app.clients.base import HttpAgentClient
from app.db.models import Visibility
from app.orchestrator.base import TurnContext
from app.orchestrator.orchestrator import LangGraphOrchestrator, _graph_builder
from contracts import SearchIoTTask
from core.config import settings
from core.llm_adapter import LLMResponse, ToolCall
from core.vectorstore import TracedOllamaEmbeddingFunction, VectorStore
from app.observability import isolated_trace_stream
from iot_agent.agent import IoTAgent
from main import app as agents_app


def tearDownModule():
    LANGFUSE.shutdown()


async def route(messages):
    if isinstance(messages[-1], HumanMessage):
        return AIMessage(content="", tool_calls=[
            {"id": str(uuid4()), "name": name, "args": {"query": messages[-1].content}}
            for name in ("search_manuals", "search_docs", "search_iot")
        ])
    return AIMessage(content="Combined answer.")


class StreamingRouter(BaseChatModel):
    model: str = "test-streaming-router"

    @property
    def _llm_type(self):
        return "test-streaming-router"

    def _generate(self, messages, **kwargs):
        raise NotImplementedError

    async def _agenerate(self, messages, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=await route(messages))])

    async def _astream(self, messages, **kwargs):
        response = await route(messages)
        if response.tool_calls:
            yield ChatGenerationChunk(message=AIMessageChunk(content="", tool_calls=response.tool_calls))
        else:
            for token in ("Combined ", "answer."):
                await asyncio.sleep(0)
                yield ChatGenerationChunk(message=AIMessageChunk(content=token))


class ParserFailingRouter(StreamingRouter):
    error_text: str = "error parsing tool call: raw='Untrusted broken output', err=invalid character 'U'"
    fail_before_tools: bool = False

    async def _agenerate(self, messages, **kwargs):
        if self.fail_before_tools or not isinstance(messages[-1], HumanMessage):
            raise ResponseError(self.error_text)
        return await super()._agenerate(messages, **kwargs)

    async def _astream(self, messages, **kwargs):
        if self.fail_before_tools or not isinstance(messages[-1], HumanMessage):
            yield ChatGenerationChunk(message=AIMessageChunk(content="Discard this partial answer."))
            raise ResponseError(self.error_text)
        async for chunk in super()._astream(messages, **kwargs):
            yield chunk


class DistributedTracingTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        LANGFUSE.flush()
        EXPORTER.clear()
        self.requests = []
        self.fail_connections = 0
        self.fail_llm = False
        self.asgi = httpx.ASGITransport(app=agents_app)
        original_client = httpx.AsyncClient

        def client_factory(**kwargs):
            return original_client(transport=httpx.MockTransport(self.dispatch), **kwargs)

        self.client_patch = patch("httpx.AsyncClient", side_effect=client_factory)
        self.client_patch.start()
        self.addCleanup(self.client_patch.stop)
        self.llm_patch = patch(
            "app.orchestrator.orchestrator._llm_with_tools", RunnableLambda(route),
        )
        self.llm_patch.start()
        self.addCleanup(self.llm_patch.stop)

        # Exercise the actual retrieval/embedding wrappers without a persistent
        # index or an Ollama server. Chroma compatibility has a separate test.
        store = VectorStore.__new__(VectorStore)
        store.embedding_fn = TracedOllamaEmbeddingFunction(model_name="test-embed")
        store.embedding_fn._client = Mock()
        store.embedding_fn._client.embed.return_value = {"embeddings": [[0.1, 0.2]]}
        store.collection = Mock()
        store.collection.get.return_value = {"metadatas": [{"language": "EN"}]}

        def query(query_texts, n_results, where):
            store.embedding_fn(query_texts)
            return {
                "documents": [["Maintenance procedure."]],
                "metadatas": [[{"doc": "manual.pdf", "page": 94}]],
            }

        store.collection.query.side_effect = query
        self.store_patch = patch("manuals_agent.agent.get_vector_store", return_value=store)
        self.store_patch.start()
        self.addCleanup(self.store_patch.stop)
        self.engine = LangGraphOrchestrator(_graph_builder.compile(), None)

    async def dispatch(self, request):
        await asyncio.sleep(0)  # Force concurrent requests to interleave.
        self.requests.append(request)
        path = request.url.path
        if path.startswith("/agents/"):
            if self.fail_connections:
                self.fail_connections -= 1
                raise httpx.ConnectError("Temporary connection failure", request=request)
            return await self.asgi.handle_async_request(request)
        if path == "/api/chat":
            if self.fail_llm:
                return httpx.Response(503)
            payload = json.loads(request.content)
            if payload.get("tools") and not any(m["role"] == "tool" for m in payload["messages"]):
                names = {t["function"]["name"] for t in payload["tools"]}
                name = next(n for n in ("search_manual", "search_orders", "search_alarms") if n in names)
                message = {"content": "", "tool_calls": [{
                    "function": {"name": name, "arguments": {"query": "maintenance"}},
                }]}
            else:
                message = {"content": "Answer from the retrieved data."}
            return httpx.Response(200, json={
                "message": message, "prompt_eval_count": 12, "eval_count": 7,
            })
        if path.endswith("/orders"):
            return httpx.Response(200, json={"results": []})
        if path.endswith("/alarms"):
            return httpx.Response(200, json={"results": [], "summary": {"matched_alarms": 0}})
        raise AssertionError(f"Unexpected HTTP request: {request.url}")

    def context(self, thread_id=None):
        return TurnContext(
            thread_id=thread_id or uuid4(), user_id=str(uuid4()), company_id="CMP-0001",
            machine_id="MCH-0001", visibility=Visibility.FULL, is_new=True,
        )

    def spans(self):
        LANGFUSE.flush()
        # Langfuse v4 may export live snapshots before the final observation.
        return list({s.context.span_id: s for s in EXPORTER.get_finished_spans()}.values())

    def assert_hierarchy(self, spans, context):
        roots = [s for s in spans if s.name == "orchestrator"]
        self.assertEqual(len(roots), 1)
        self.assertEqual({s.context.trace_id for s in spans}, {roots[0].context.trace_id})
        by_id = {s.context.span_id: s for s in spans}
        for agent, tool in (("ManualsAgent", "search_manuals"), ("DocsAgent", "search_docs"), ("IoTAgent", "search_iot")):
            child = next(s for s in spans if s.name == agent)
            http = by_id[child.parent.span_id]
            self.assertTrue(http.name.endswith(".http"))
            self.assertEqual(by_id[http.parent.span_id].name, tool)
            self.assertEqual(child.attributes["langfuse.observation.type"], "agent")
            self.assertEqual(child.attributes["user.id"], context.user_id)
            self.assertEqual(child.attributes["session.id"], str(context.thread_id))
        names = {s.name for s in spans}
        self.assertTrue({"ollama.chat", "ollama.embed", "manuals.retrieve", "manuals.languages",
                         "backoffice.docs.get", "backoffice.iot.get", "build_response"} <= names)
        generations = [s for s in spans if s.name == "ollama.chat"]
        self.assertEqual(len(generations), 6)
        for generation in generations:
            self.assertEqual(generation.attributes["langfuse.observation.model.name"], "test-model")
            self.assertEqual(json.loads(generation.attributes["langfuse.observation.usage_details"]), {"input": 12, "output": 7})
        for request in self.requests:
            if request.url.path.startswith("/agents/"):
                self.assertIn("traceparent", request.headers)
                self.assertIn("baggage", request.headers)
            else:
                self.assertNotIn("baggage", request.headers)

    async def test_full_turn_contains_all_agents_and_their_operations(self):
        context = self.context()
        response = await self.engine.handle(context, "maintenance")
        self.assertEqual(response.answer, "Combined answer.")
        self.assert_hierarchy(self.spans(), context)
        self.assertFalse(trace.get_current_span().get_span_context().is_valid)

    async def test_streaming_preserves_the_same_hierarchy(self):
        context = self.context()
        events = []
        async for event in self.engine.handle_stream(context, "maintenance"):
            events.append(event)
            self.assertFalse(trace.get_current_span().get_span_context().is_valid)
        self.assertEqual(events[-1]["type"], "done")
        self.assertTrue(any(e["type"] == "sources" for e in events))
        self.assert_hierarchy(self.spans(), context)

    async def test_token_streaming_keeps_llm_and_agents_in_one_trace(self):
        context = self.context()
        with patch("app.orchestrator.orchestrator._llm_with_tools", StreamingRouter()):
            events = [event async for event in self.engine.handle_stream(context, "maintenance")]
        self.assertEqual("".join(e["text"] for e in events if e["type"] == "token"), "Combined answer.")
        self.assert_hierarchy(self.spans(), context)

    async def test_tool_parse_error_recovers_from_existing_results_in_non_streaming_turn(self):
        fallback = AsyncMock(wraps=StreamingRouter().ainvoke)
        with (
            patch("app.orchestrator.orchestrator._llm_with_tools", ParserFailingRouter()),
            patch("app.orchestrator.orchestrator._llm", Mock(ainvoke=fallback)),
            self.assertLogs("app.orchestrator.orchestrator", level="WARNING"),
        ):
            response = await self.engine.handle(self.context(), "maintenance")
        self.assertEqual(response.answer, "Combined answer.")
        self.assertTrue(response.sources)
        fallback.assert_awaited_once()
        messages = fallback.call_args.args[0]
        self.assertIn("using only the tool results", messages[0].content)
        self.assertNotIn("Untrusted broken output", str(messages))
        self.assertEqual(len([r for r in self.requests if r.url.path.startswith("/agents/")]), 3)

    async def test_stream_recovery_resets_partial_answer_and_keeps_sources_and_trace(self):
        context = self.context()
        with (
            patch("app.orchestrator.orchestrator._llm_with_tools", ParserFailingRouter()),
            patch("app.orchestrator.orchestrator._llm", StreamingRouter()),
            self.assertLogs("app.orchestrator.orchestrator", level="WARNING"),
        ):
            events = [event async for event in self.engine.handle_stream(context, "maintenance")]
        self.assertEqual(sum(e["type"] == "reset" for e in events), 1)
        self.assertFalse(any(e["type"] == "error" for e in events))
        text = ""
        for event in events:
            if event["type"] == "reset":
                self.assertIn("Discard this partial answer.", text)
                text = ""
            elif event["type"] == "token":
                text += event["text"]
        self.assertEqual(text, "Combined answer.")
        self.assertTrue(next(e for e in events if e["type"] == "sources")["sources"])
        self.assertEqual(len([r for r in self.requests if r.url.path.startswith("/agents/")]), 3)
        spans = self.spans()
        self.assert_hierarchy(spans, context)
        self.assertIn("orchestrator.final_synthesis_recovery", {s.name for s in spans})
        self.assertTrue(any(s.status.status_code.name == "ERROR" for s in spans))

    async def test_unrelated_error_or_missing_current_turn_results_does_not_recover(self):
        for model in (ParserFailingRouter(error_text="model unavailable"), ParserFailingRouter(fail_before_tools=True)):
            fallback = AsyncMock()
            with (
                patch("app.orchestrator.orchestrator._llm_with_tools", model),
                patch("app.orchestrator.orchestrator._llm", Mock(ainvoke=fallback)),
                self.assertLogs("app.orchestrator.orchestrator", level="ERROR"),
            ):
                events = [event async for event in self.engine.handle_stream(self.context(), "maintenance")]
            fallback.assert_not_awaited()
            self.assertFalse(any(e["type"] == "reset" for e in events))
            self.assertTrue(any(e["type"] == "error" and not e["recoverable"] for e in events))

    async def test_failed_recovery_is_not_retried_again(self):
        fallback = AsyncMock(side_effect=ResponseError("error parsing tool call: invalid output"))
        with (
            patch("app.orchestrator.orchestrator._llm_with_tools", ParserFailingRouter()),
            patch("app.orchestrator.orchestrator._llm", Mock(ainvoke=fallback)),
            self.assertLogs("app.orchestrator.orchestrator", level="WARNING"),
        ):
            events = [event async for event in self.engine.handle_stream(self.context(), "maintenance")]
        fallback.assert_awaited_once()
        self.assertEqual(sum(e["type"] == "reset" for e in events), 1)
        self.assertTrue(any(e["type"] == "error" and not e["recoverable"] for e in events))

    async def test_sequential_turns_in_one_task_do_not_reuse_the_previous_trace(self):
        context = self.context()
        await self.engine.handle(context, "maintenance")
        await self.engine.handle(context, "maintenance again")
        roots = [s for s in self.spans() if s.name == "orchestrator"]
        self.assertEqual(len({s.context.trace_id for s in roots}), 2)
        self.assertTrue(all(s.parent is None for s in roots))

    async def test_stream_can_be_closed_by_another_task_without_context_leak(self):
        closed = []

        async def source():
            with LANGFUSE.start_as_current_observation(name="stream-source"):
                try:
                    yield "chunk"
                finally:
                    closed.append(True)

        stream = isolated_trace_stream(source())
        self.assertEqual(await anext(stream), "chunk")
        self.assertFalse(trace.get_current_span().get_span_context().is_valid)
        await asyncio.create_task(stream.aclose())
        self.assertEqual(closed, [True])
        self.assertFalse(trace.get_current_span().get_span_context().is_valid)

    async def test_cancelling_a_turn_restores_the_callers_context(self):
        entered = asyncio.Event()

        async def blocked(messages):
            entered.set()
            await asyncio.Event().wait()

        with patch("app.orchestrator.orchestrator._llm_with_tools", RunnableLambda(blocked)):
            task = asyncio.create_task(self.engine.handle(self.context(), "maintenance"))
            await entered.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertFalse(trace.get_current_span().get_span_context().is_valid)

    async def test_export_failure_does_not_break_the_answer(self):
        with patch.object(EXPORTER, "export", side_effect=RuntimeError("Langfuse unavailable")):
            with self.assertLogs("opentelemetry", level="ERROR"):
                response = await self.engine.handle(self.context(), "maintenance")
                LANGFUSE.flush()
        self.assertEqual(response.answer, "Combined answer.")

    async def test_existing_chroma_collection_accepts_the_traced_embedding_function(self):
        import chromadb
        from chromadb.config import Settings as ChromaSettings
        from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(settings, "CHROMA_PATH", directory),
            patch("ollama.Client.embed", return_value={"embeddings": [[0.1, 0.2]]}),
        ):
            client = chromadb.PersistentClient(path=directory, settings=ChromaSettings(anonymized_telemetry=False))
            collection = client.get_or_create_collection("manuals", embedding_function=OllamaEmbeddingFunction(
                url=settings.OLLAMA_BASE_URL, model_name=settings.EMBEDDING_MODEL, timeout=120,
            ))
            collection.add(ids=["one"], documents=["Maintenance procedure."], metadatas=[{
                "doc": "manual.pdf", "page": 94, "machine_id": "MCH-0001", "language": "EN",
            }])
            # Reopen the persisted original collection using the production wrapper.
            with patch("core.vectorstore.chromadb.PersistentClient", return_value=client):
                store = VectorStore()
            self.assertEqual(store.get_languages({"machine_id": "MCH-0001"}), ["EN"])
            self.assertEqual(store.query("maintenance", k=1, where={"machine_id": "MCH-0001"})[0]["page"], 94)
        spans = self.spans()
        embedding = next(s for s in spans if s.name == "ollama.embed")
        retrieval = next(s for s in spans if s.name == "manuals.retrieve")
        self.assertEqual(embedding.parent.span_id, retrieval.context.span_id)

    async def test_concurrent_turns_have_separate_traces_even_in_one_session(self):
        thread_id = uuid4()
        contexts = [self.context(thread_id), self.context(thread_id)]
        await asyncio.gather(*(self.engine.handle(c, "maintenance") for c in contexts))
        spans = self.spans()
        roots = [s for s in spans if s.name == "orchestrator"]
        self.assertEqual(len({s.context.trace_id for s in roots}), 2)
        for context in contexts:
            root = next(s for s in roots if s.attributes["user.id"] == context.user_id)
            self.assert_hierarchy([s for s in spans if s.context.trace_id == root.context.trace_id], context)

    async def test_connection_retry_stays_in_the_same_trace(self):
        self.fail_connections = 1
        with patch.object(HttpAgentClient._post.retry, "wait", wait_none()):
            await self.engine.handle(self.context(), "maintenance")
        spans = self.spans()
        attempts = [s for s in spans if s.name.endswith(".http")]
        self.assertEqual(len(attempts), 4)
        self.assertEqual(len({s.context.trace_id for s in spans}), 1)
        self.assertEqual(sum(s.status.status_code.name == "ERROR" for s in attempts), 1)

    async def test_llm_failure_is_visible_and_context_is_detached(self):
        self.fail_llm = True
        with LANGFUSE.start_as_current_observation(name="caller"):
            parent = trace.get_current_span().get_span_context()
            headers = {"traceparent": f"00-{parent.trace_id:032x}-{parent.span_id:016x}-01"}
            async with httpx.AsyncClient() as client:
                with self.assertRaises(httpx.HTTPStatusError):
                    await client.post("http://agents/agents/iot/search", headers=headers,
                                      json={"query": "alarms", "machine_id": "MCH-0001"})
            self.assertEqual(trace.get_current_span().get_span_context(), parent)
        errors = [s for s in self.spans() if s.status.status_code.name == "ERROR"]
        self.assertTrue({"ollama.chat", "IoTAgent"} <= {s.name for s in errors})

    async def test_missing_or_invalid_parent_starts_an_independent_trace(self):
        for headers in ({}, {"traceparent": "invalid"}):
            with LANGFUSE.start_as_current_observation(name="unrelated-caller"):
                parent = trace.get_current_span().get_span_context()
                async with httpx.AsyncClient() as client:
                    response = await client.post("http://agents/agents/iot/search", headers=headers,
                                                 json={"query": "alarms", "machine_id": "MCH-0001"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(trace.get_current_span().get_span_context(), parent)
        agents = [s for s in self.spans() if s.name == "IoTAgent"]
        self.assertEqual(len(agents), 2)
        self.assertTrue(all(s.parent is None for s in agents))
        self.assertEqual(len({s.context.trace_id for s in agents}), 2)

    async def test_tool_error_result_and_budget_synthesis_are_recorded(self):
        llm = Mock()

        async def complete(messages, tools=None):
            if tools:
                return LLMResponse(tool_calls=[ToolCall(name="unknown", arguments={})])
            return LLMResponse(content="Cannot answer.")

        llm.complete = complete
        with patch.object(settings, "MAX_ITERATIONS", 1):
            response = await IoTAgent(llm).run(SearchIoTTask(query="alarms", machine_id="MCH-0001"))
        self.assertEqual(response.answer, "Cannot answer.")
        spans = self.spans()
        tool = next(s for s in spans if s.name == "unknown")
        self.assertEqual(tool.attributes["langfuse.observation.level"], "ERROR")
        self.assertIn("agent.final_synthesis", {s.name for s in spans})

    async def test_disabled_tracing_does_not_change_the_agent_response(self):
        # Use the existing project resource; a second project would intentionally
        # make SDK get_client() ambiguous for the later backend tests.
        disabled = Langfuse(tracing_enabled=False)
        llm = Mock()

        async def complete(messages, tools=None):
            return LLMResponse(content="A normal answer.")

        llm.complete = complete
        with patch("core.base_agent.get_langfuse", return_value=disabled):
            response = await IoTAgent(llm).run(SearchIoTTask(query="alarms", machine_id="MCH-0001"))
        self.assertEqual(response.answer, "A normal answer.")
        self.assertEqual(self.spans(), [])


if __name__ == "__main__":
    unittest.main()
