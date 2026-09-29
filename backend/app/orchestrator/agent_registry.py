import json
 
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
 
from app.clients.docs_client import DocsClient
from app.clients.exceptions import AgentUnavailableError
from app.clients.iot_client import IoTClient
from app.clients.manuals_client import ManualsClient
 
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
    return _result({"error": message})
 
 
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
    machine_id, _ = _scope(config)
    try:
        result = await manuals_client.search(query=query, machine_id=machine_id)
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
    machine_id, company_id = _scope(config)
    try:
        result = await docs_client.search(
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
    machine_id, _ = _scope(config)
    try:
        result = await iot_client.search(query=query, machine_id=machine_id)
    except AgentUnavailableError as exc:
        return _error(f"The IoT service is not available: {exc}")
 
    return _result({
        "answer": result.answer,
        "observations": [o.model_dump() for o in result.observations],
        "confidence": result.confidence,
    })
 
 
AGENT_TOOLS = [search_manuals, search_docs, search_iot]
 
