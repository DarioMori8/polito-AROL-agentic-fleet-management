"""Langfuse observations and W3C context propagation at the HTTP boundary."""

from functools import lru_cache

from langfuse import Langfuse
from opentelemetry import context
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from core.config import settings


@lru_cache(maxsize=1)
def get_langfuse() -> Langfuse:
    return Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        base_url=settings.LANGFUSE_HOST,
        tracing_enabled=settings.LANGFUSE_TRACING_ENABLED,
    )


_propagator = CompositePropagator([
    TraceContextTextMapPropagator(), W3CBaggagePropagator(),
])


class AgentTraceContextMiddleware:
    """Restore only tracing context; task authorization stays in the task schema.

    Pure ASGI middleware keeps the context in the request task. Always detach,
    including on exceptions/cancellation, so concurrent calls remain isolated.
    An absent or malformed traceparent produces a fresh trace in BaseAgent.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/agents/"):
            return await self.app(scope, receive, send)

        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
            if key.lower() in (b"traceparent", b"tracestate", b"baggage")
        }
        token = context.attach(_propagator.extract(headers, context=context.Context()))
        try:
            await self.app(scope, receive, send)
        finally:
            context.detach(token)
