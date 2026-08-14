from langchain_core.tools import tool
 
from app.clients.exceptions import AgentUnavailableError
from app.clients.manuals_client import ManualsClient
 
manuals_client = ManualsClient()


@tool(response_format="content_and_artifact")
async def search_manuals(query: str, machine_id: str) -> tuple[str, dict]:
    """ Search the use and maintenance manuals of a specific machine.

        Use it when the user asks how to operate, configure or 
        troubleshoot a machine, based on the official 
        documentation (error codes, procedures, settings, safety).
 
    Args:
        query: The user's question riformulate as query.
        machine_id: The identifier of the machine the question refers to.
    """
    try:
        result= await manuals_client.search(query=query, machine_id=machine_id)
    except AgentUnavailableError as exc:
        error= {"error": f"The Manual Service is not available:{exc}"}
        return str(error), error

    artifact= {
        "answer": result.answer,
        "citations": [c.model_dump() for c in result.citations],
        "confidence": result.confidence,
    }

    return str(artifact), artifact

from app.clients.docs_client import DocsClient

docs_client = DocsClient()


@tool(response_format="content_and_artifact")
async def search_docs(query: str, machine_id: str) -> tuple[str, dict]:
    """Search commercial and contractual records for a specific machine.

    Use it when the user asks about quotes, orders, delivery status,
    warranty terms, payment terms, or contractual documents — anything
    tied to the commercial relationship rather than how the machine
    physically works. Do NOT use it for operating, configuration or
    troubleshooting questions (that is the manuals agent).

    Args:
        query: The user's question reformulated as a query.
        machine_id: The identifier of the machine the question refers to.
    """
    try:
        result = await docs_client.search(query=query, machine_id=machine_id)
    except AgentUnavailableError as exc:
        error = {"error": f"The Docs Service is not available: {exc}"}
        return str(error), error

    artifact = {
        "answer": result.answer,
        "sources": [s.model_dump() for s in result.sources],
        "confidence": result.confidence,
    }

    return str(artifact), artifact


AGENT_TOOLS = [search_manuals, search_docs]



