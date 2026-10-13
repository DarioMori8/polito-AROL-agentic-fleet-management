"""Bridge LangChain's active tool observation to the remote agents service."""

import asyncio
from contextlib import contextmanager
from contextvars import copy_context

from langfuse import propagate_attributes
from langfuse.langchain import CallbackHandler
from opentelemetry import context
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator


def new_callback_handler() -> CallbackHandler:
    handler = CallbackHandler()
    # LangChain otherwise dispatches synchronous callbacks to an executor.
    # Their ContextVar changes would not reach the asynchronous tool body.
    handler.run_inline = True
    return handler


@contextmanager
def graph_trace_context():
    # Graph callbacks may finish in a different task from the one that started
    # them. Restore the caller's entire context even if a callback leaves an
    # ended span attached. Each chat turn starts its own trace.
    token = context.attach(context.Context())
    try:
        yield
    finally:
        context.detach(token)


async def isolated_trace_stream(stream):
    """Run every graph step and close in one private Context.

    Reusing the same contextvars.Context preserves SDK tokens across yields,
    even when the consumer closes the stream from another task. Awaiting each
    step also preserves backpressure and forwards cancellation to the graph.
    """
    stream_context = copy_context()
    stream_context.run(context.attach, context.Context())
    try:
        while True:
            try:
                item = await asyncio.create_task(anext(stream), context=stream_context)
            except StopAsyncIteration:
                return
            yield item
    finally:
        await asyncio.create_task(stream.aclose(), context=stream_context)


_propagator = CompositePropagator([
    TraceContextTextMapPropagator(), W3CBaggagePropagator(),
])


def agent_trace_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    _propagator.inject(headers)
    return headers


async def traced_agent_search(client, config, **kwargs):
    # Baggage is injected only into backend -> agents requests, never into
    # arbitrary outbound calls. It carries observability, not authorization.
    metadata = config.get("metadata", {})
    with propagate_attributes(
        user_id=metadata.get("langfuse_user_id"),
        session_id=metadata.get("langfuse_session_id"),
        as_baggage=True,
    ):
        return await client.search(**kwargs)
