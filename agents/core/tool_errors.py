"""Expected tool failures exposed to the model without internal service details."""

from json import JSONDecodeError

import httpx
from chromadb.errors import ChromaError
from ollama import ResponseError as OllamaResponseError


EXPECTED_TOOL_ERRORS = (
    httpx.HTTPError, ConnectionError, TimeoutError, ChromaError,
    OllamaResponseError, JSONDecodeError,
)

TOOL_ERROR_INSTRUCTIONS = """
Tool failures contain error and error_type; they are not empty search results.
For invalid_arguments, correct the arguments using the tool schema before retrying.
For access_denied, do not retry or seek the same data through another tool.
For service_unavailable or timeout, at most one retry is useful; if it still
fails, explain that the source could not be consulted. Never invent missing data.
Successful results from other tools remain usable, but state any missing part.
"""


def tool_error(error_type: str, message: str) -> dict:
    return {"error": message, "error_type": error_type}


def describe_tool_error(exc: Exception) -> dict:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in (400, 422):
            result = tool_error(
                "invalid_arguments",
                "The data service rejected the filters. Check allowed values and "
                "ISO date formats in the tool schema, then correct the arguments.",
            )
        elif status in (401, 403):
            result = tool_error("access_denied", "The data service denied access to this resource.")
        elif status == 404:
            result = tool_error("not_found", "The requested resource was not found by the data service.")
        elif status == 429 or status >= 500:
            result = tool_error("service_unavailable", "The data service is temporarily unavailable.")
        else:
            result = tool_error("request_failed", "The data service could not process the request.")
        return {**result, "http_status": status}
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return tool_error("timeout", "The tool timed out while waiting for its data source.")
    if isinstance(exc, JSONDecodeError):
        return tool_error("invalid_response", "The data service returned an unreadable response.")
    if isinstance(exc, ChromaError):
        return tool_error("retrieval_failed", "The manual index could not complete the search.")
    if isinstance(exc, OllamaResponseError):
        return tool_error("service_unavailable", "The embedding service could not complete the search.")
    return tool_error("service_unavailable", "The tool could not communicate with its data source.")
