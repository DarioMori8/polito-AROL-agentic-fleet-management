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

AGENT_TOOLS = [search_manuals]


