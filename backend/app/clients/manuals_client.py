import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from contracts import SearchManualResponse
from app.clients.base import ManualClientBase
from app.clients.exceptions import AgentUnavailableError


class ManualsClient(ManualClientBase):
    """
    HTTP client responsible for talking to the Manuals Agent service.

    This class hides all networking details (URL, timeouts, retries,
    error handling) behind a simple `search()` method, so the rest of
    the backend (the orchestrator) never needs to know it's making an
    HTTP call under the hood.
    """

    def __init__(self):
        # Base URL of the Manuals Agent service, read from environment
        # variables via Settings.
        self.base_url = settings.MANUALS_AGENT_URL

    @retry(
        # Only retry when the agent is unreachable. Timeouts are deliberately
        # excluded: the agent is not flaky, it is slow — a full RAG turn on a
        # 20B model takes tens of seconds — so retrying restarts the whole
        # generation from scratch, piles concurrent work onto Ollama and makes
        # every attempt slower than the one before. Retrying HTTP error codes
        # would be pointless too: those indicate a logic error, not a glitch.
        retry=retry_if_exception_type(httpx.ConnectError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        # reraise=True ensures that, after exhausting all retries, the
        # original exception (not tenacity's own RetryError) is raised,
        # so the try/except block in search() still catches it correctly.
        reraise=True,
    )
    async def _post(self, url: str, payload: dict) -> httpx.Response:
        """
        Low-level HTTP POST call, wrapped with automatic retry.
        Kept separate from search() so that tenacity only retries the
        raw network call, not the response parsing/validation logic.
        """
        # Sized for the worst case of a 20B model composing an answer over
        # retrieved manual chunks, not for the average case: a measured warm
        # request already sits around 27s.
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(url, json=payload)

        response.raise_for_status()
        return response

    async def search(self, query: str, machine_id: str) -> SearchManualResponse:
        """
        Sends a search request to the Manuals Agent and returns a
        validated SearchManualResponse.

        Raises:
            AgentUnavailableError: if the agent is unreachable, times
            out, or responds with an error status, even after retries.
        """
        payload = {"query": query, "machine_id": machine_id}
        url = f"{self.base_url}/agents/manuals/search"

        try:
            response = await self._post(url, payload)
        except httpx.TimeoutException as e:
            # Agent took too long to respond (e.g. slow LLM inference)
            raise AgentUnavailableError(f"Timeout while contacting Manuals agent: {e}") from e
        except httpx.ConnectError as e:
            # Agent process is down or unreachable at the configured URL
            raise AgentUnavailableError(f"Could not reach Manuals agent: {e}") from e
        except httpx.HTTPStatusError as e:
            # Agent responded, but with an error status code
            raise AgentUnavailableError(f"Manuals agent returned an error: {e}") from e

        # Parse and validate the JSON body against our shared Pydantic schema
        return SearchManualResponse.model_validate(response.json())