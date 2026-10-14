from typing import ClassVar, Generic, TypeVar

import httpx
from langfuse import get_client
from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings
from app.clients.exceptions import AgentUnavailableError
from app.observability import agent_trace_headers

T = TypeVar("T", bound=BaseModel)


class HttpAgentClient(Generic[T]):
    """
    Shared HTTP transport for downstream agents: POST-with-retry, mapping of
    every failure onto AgentUnavailableError, and validation of the response
    against a Pydantic schema.

    Concrete clients only declare three things — the endpoint path, the
    response schema, and a human-readable agent name for error messages — and
    inherit all the networking behaviour.
    """

    path: ClassVar[str]
    response_schema: ClassVar[type[BaseModel]]
    agent_name: ClassVar[str]

    def __init__(self, base_url: str | None = None):
        # Injectable for tests; defaults to the configured agents service.
        self.base_url = (base_url or settings.AGENTS_SERVICE_URL).rstrip("/")

    # The retry covers ONLY the raw network I/O. Retrying a higher-level
    # method would repeat parsing, validation and observability side effects.
    # Only transient failures are retried: a 4xx/5xx answer is a real answer.
    @retry(
        retry=retry_if_exception_type((httpx.ConnectTimeout, httpx.ConnectError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def _post(self, url: str, payload: dict) -> httpx.Response:
        # A separate child observation for every network attempt. The context
        # is captured here, under the current tool, never in a global trace id.
        with get_client().start_as_current_observation(
            name=f"{self.agent_name}.http", as_type="span",
            input=payload, metadata={"method": "POST", "url": url},
        ) as observation:
            # A read timeout may leave inference running downstream, so only the
            # connect phase is short (and retried); the read waits for the agent.
            timeout = httpx.Timeout(settings.AGENTS_REQUEST_TIMEOUT_SECONDS, connect=5.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload, headers=agent_trace_headers())
            observation.update(metadata={"http_status": response.status_code})
            response.raise_for_status()
            return response

    async def _request(self, payload: dict) -> T:
        """
        Everything that is the same for every agent. Kept separate from
        search() so that a client whose task carries extra fields (docs, with
        its tenant) can build its own payload and still reuse the transport.
        """
        url = f"{self.base_url}{self.path}"

        try:
            response = await self._post(url, payload)
        except httpx.TimeoutException as e:
            raise AgentUnavailableError(f"Timeout while contacting {self.agent_name} agent: {e}") from e
        except httpx.ConnectError as e:
            raise AgentUnavailableError(f"Could not reach {self.agent_name} agent: {e}") from e
        except httpx.HTTPStatusError as e:
            raise AgentUnavailableError(f"{self.agent_name} agent returned an error: {e}") from e

        # A malformed body (not JSON, or JSON of the wrong shape) is also an
        # unusable answer, not a crash: it must reach the tool as the same
        # error type as a network failure.
        try:
            return self.response_schema.model_validate_json(response.content)
        except ValidationError as e:
            raise AgentUnavailableError(
                f"{self.agent_name} agent returned an invalid response: {e}"
            ) from e

    async def search(self, query: str, machine_id: str) -> T:
        """Default task shape: the two fields every agent task shares."""
        return await self._request({"query": query, "machine_id": machine_id})
