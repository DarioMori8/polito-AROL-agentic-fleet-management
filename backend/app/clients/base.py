from abc import ABC, abstractmethod
from typing import Generic, TypeVar

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from pydantic import BaseModel

from app.config import settings
from app.clients.exceptions import AgentUnavailableError

T = TypeVar("T", bound=BaseModel)


class AgentClientBase(ABC, Generic[T]):
    """Contract: any client that talks to a downstream agent exposes search()."""

    @abstractmethod
    async def search(self, query: str, machine_id: str) -> T:
        ...


class HttpAgentClient(AgentClientBase[T]):
    """
    Shared HTTP transport for downstream agents: POST-with-retry, mapping
    of transient network failures to AgentUnavailableError, and response
    validation against a Pydantic schema.

    Concrete clients only declare three things — the endpoint path, the
    response schema, and a human-readable agent name for error messages —
    and inherit all the networking behaviour.
    """

    path: str
    response_schema: type[T]
    agent_name: str

    def __init__(self):
        self.base_url = settings.AGENTS_SERVICE_URL

    @retry(
        retry=retry_if_exception_type((httpx.ConnectTimeout, httpx.ConnectError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def _post(self, url: str, payload: dict) -> httpx.Response:
        # A read timeout may leave inference running downstream. Retrying it
        # would enqueue duplicate work on the same local model.
        timeout = httpx.Timeout(settings.AGENTS_REQUEST_TIMEOUT_SECONDS, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload)
        response.raise_for_status()
        return response

    async def _request(self, payload: dict) -> T:
        """
        Everything that is the same for every agent: POST with retry, mapping
        of httpx failures onto AgentUnavailableError, and validation against
        the concrete client's response schema.

        Kept separate from search() so that a client whose task carries extra
        fields (docs, with its tenant) can build its own payload and still
        reuse all the transport behaviour.
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

        return self.response_schema.model_validate(response.json())

    async def search(self, query: str, machine_id: str) -> T:
        """Default shape: the two fields every agent task shares."""
        return await self._request({"query": query, "machine_id": machine_id})