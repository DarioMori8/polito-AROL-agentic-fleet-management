import json

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langfuse import get_client

from app.clients.docs_client import DocsClient
from app.clients.exceptions import AgentUnavailableError
from app.clients.iot_client import IoTClient
from app.clients.manuals_client import ManualsClient
from app.observability import traced_agent_search
from app.security.access import DataDomain, denial_message, is_allowed

manuals_client = ManualsClient()
docs_client = DocsClient()
iot_client = IoTClient()


# --- Scope injection
#
# machine_id and company_id are NOT tool arguments. Both are resolved by the
# orchestrator before the graph starts (machine checked against the user's
# company, thread pinned to that machine) and passed in the RunnableConfig.
# A parameter annotated as RunnableConfig is injected by LangChain and left
# out of the schema the LLM sees, so the model can neither set, widen nor
# forge the scope: the only thing it chooses is the query.

def _scope(config: RunnableConfig) -> tuple[str, str]:
    configurable = config.get("configurable", {})
    return configurable["machine_id"], configurable["company_id"]


def _result(artifact: dict) -> tuple[str, dict]:
    # content (what the LLM reads) and artifact (what the frontend receives)
    # carry the same data; JSON keeps the content readable and unambiguous.
    return json.dumps(artifact, ensure_ascii=False), artifact


def _error(message: str) -> tuple[str, dict]:
    # These failures are returned as tool results, so the callback does not
    # receive an exception. Explicitly mark the active tool observation.
    get_client().update_current_span(level="ERROR", status_message=message)
    return _result({"error": message})


# --- Access control (visibility)
#
# Every tool declares the data domain it reads and calls _denied() FIRST,
# before any network call. The visibility comes from the RunnableConfig, set
# by the orchestrator from the authenticated user: like the tenant, it is
# decided by the server and invisible to the model.
#
# This is the enforcement point, and it is deliberately NOT the model: all
# tools stay visible to the LLM, which may call any of them; a call outside
# the user's profile is stopped here, the agent is never contacted, and an
# explicit denial comes back — never an empty result, which would read as
# "no data exists".

def _denied(config: RunnableConfig, domain: DataDomain) -> tuple[str, dict] | None:
    visibility = config.get("configurable", {}).get("visibility")
    if is_allowed(visibility, domain):
        return None
    return _result({
        "denied": {"domain": domain.value, "message": denial_message(domain)},
    })


# --- Tools

@tool(response_format="content_and_artifact")
async def search_manuals(query: str, config: RunnableConfig) -> tuple[str, dict]:
    """Search the use and maintenance manual of the machine in this conversation.

    Use it when the user asks how to operate, configure or troubleshoot the
    machine, based on the official documentation (error codes, procedures,
    settings, safety).

    The manuals are written in ENGLISH and searched semantically: a query in
    another language, or in everyday wording, matches the wrong pages.

    Args:
        query: The user's question rewritten as an English search query that
            uses the technical terms a machine manual would use (e.g. Italian
            "coppia di serraggio" -> "tightening torque adjustment", not
            "clamping torque"). Keep it short and specific.
    """
    if (denied := _denied(config, DataDomain.IDENTITY)) is not None:
        return denied
    machine_id, _ = _scope(config)
    try:
        result = await traced_agent_search(
            manuals_client, config, query=query, machine_id=machine_id,
        )
    except AgentUnavailableError as exc:
        return _error(f"The Manuals service is not available: {exc}")

    return _result({
        "answer": result.answer,
        "citations": [c.model_dump() for c in result.citations],
        "confidence": result.confidence,
    })


@tool(response_format="content_and_artifact")
async def search_docs(query: str, config: RunnableConfig) -> tuple[str, dict]:
    """Search commercial and contractual records for the machine in this conversation.

    Use it when the user asks about quotes, orders, delivery status,
    warranty terms, payment terms, or contractual documents — anything
    tied to the commercial relationship rather than how the machine
    physically works. Do NOT use it for operating, configuration or
    troubleshooting questions (that is the manuals tool), nor for live
    telemetry, alarms or maintenance tickets (that is the iot tool).

    Args:
        query: The user's question reformulated as a search query.
    """
    if (denied := _denied(config, DataDomain.COMMERCIAL)) is not None:
        return denied
    machine_id, company_id = _scope(config)
    try:
        result = await traced_agent_search(
            docs_client, config,
            query=query, machine_id=machine_id, company_id=company_id
        )
    except AgentUnavailableError as exc:
        return _error(f"The Docs service is not available: {exc}")

    return _result({
        "answer": result.answer,
        "sources": [s.model_dump() for s in result.sources],
        "confidence": result.confidence,
    })


@tool(response_format="content_and_artifact")
async def search_iot(query: str, config: RunnableConfig) -> tuple[str, dict]:
    """Search live operational data for the machine in this conversation.

    Use it when the user asks about what the machine is actually doing or
    has done: current status, telemetry (production rate, uptime,
    temperature, energy), active or historical alarms, and maintenance
    tickets. Use it for questions about readings, trends, alarm events,
    or ticket status over a time window.

    Do NOT use it for how to operate, configure or repair the machine
    (that is the manuals tool), nor for quotes, orders, warranty or
    contracts (that is the docs tool). If an alarm is active and the
    user wants the fix procedure, this tool finds the alarm; the manuals
    tool supplies the procedure.

    Args:
        query: The user's question reformulated as a search query.
    """
    if (denied := _denied(config, DataDomain.OPERATIONAL)) is not None:
        return denied
    machine_id, _ = _scope(config)
    try:
        result = await traced_agent_search(
            iot_client, config, query=query, machine_id=machine_id,
        )
    except AgentUnavailableError as exc:
        return _error(f"The IoT service is not available: {exc}")

    return _result({
        "answer": result.answer,
        "observations": [o.model_dump() for o in result.observations],
        "confidence": result.confidence,
    })


AGENT_TOOLS = [search_manuals, search_docs, search_iot]
