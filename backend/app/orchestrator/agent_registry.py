from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

 
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

    # Keep full snippets in the artifact for the UI, but avoid flooding the
    # routing model's context with repeated excerpts from every search attempt.
    content = {
        **artifact,
        "citations": [{"doc": c.doc, "page": c.page} for c in result.citations],
    }
    return str(content), artifact



from app.clients.docs_client import DocsClient

docs_client = DocsClient()


@tool(response_format="content_and_artifact")
async def search_docs(query: str, machine_id: str, config: RunnableConfig) -> tuple[str, dict]:
    """Search commercial and contractual records for a specific machine.

    Use it when the user asks about quotes, orders, delivery status,
    warranty terms, payment terms, or contractual documents — anything
    tied to the commercial relationship rather than how the machine
    physically works. Do NOT use it for operating, configuration or
    troubleshooting questions (that is the manuals agent), nor for live
    telemetry, alarms or maintenance tickets (that is the iot agent).

    Args:
        query: The user's question reformulated as a query.
        machine_id: The identifier of the machine the question refers to.
    """
    # The tenant boundary comes from the runtime config, resolved by the
    # orchestrator from our own domain DB — never from the model. It is
    # deliberately absent from this tool's schema, so the LLM cannot set,
    # widen or forge it.
    company_id = config.get("configurable", {}).get("company_id")
    if not company_id:
        error = {"error": "Cannot query commercial records: the machine is not associated with any customer company."}
        return str(error), error

    try:
        result = await docs_client.search(
            query=query, machine_id=machine_id, company_id=company_id
        )
    except AgentUnavailableError as exc:
        error = {"error": f"The Docs Service is not available: {exc}"}
        return str(error), error

    artifact = {
        "answer": result.answer,
        "sources": [s.model_dump() for s in result.sources],
        "confidence": result.confidence,
    }

    return str(artifact), artifact




from app.clients.iot_client import IoTClient

iot_client = IoTClient()


@tool(response_format="content_and_artifact")
async def search_iot(query: str, machine_id: str) -> tuple[str, dict]:
    """Search live operational data for a specific machine.

    Use it when the user asks about what the machine is actually doing or
    has done: current status, telemetry (production rate, uptime,
    temperature, energy), active or historical alarms, and maintenance
    tickets. Use it for questions about readings, trends, alarm events,
    or ticket status over a time window.

    Do NOT use it for how to operate, configure or repair the machine
    (that is the manuals agent), nor for quotes, orders, warranty or
    contracts (that is the docs agent). If an alarm is active and the
    user wants the fix procedure, this agent finds the alarm; the manuals
    agent supplies the procedure.

    Args:
        query: The user's question reformulated as a query.
        machine_id: The identifier of the machine the question refers to.
    """
    try:
        result = await iot_client.search(query=query, machine_id=machine_id)
    except AgentUnavailableError as exc:
        error = {"error": f"The IoT Service is not available: {exc}"}
        return str(error), error

    artifact = {
        "answer": result.answer,
        "observations": [o.model_dump() for o in result.observations],
        "confidence": result.confidence,
    }

    return str(artifact), artifact


AGENT_TOOLS = [search_manuals, search_docs, search_iot]