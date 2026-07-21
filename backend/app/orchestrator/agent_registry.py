from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app.clients.manuals_client import ManualsClient

ToolHandler = Callable[[dict], Awaitable[dict]]


@dataclass
class AgentTool:
    name: str
    description: str
    parameters: dict[str, Any] #JSON schema 
    handler: ToolHandler


manuals_client= ManualsClient()


async def _handle_search_manuals(arguments: dict)-> dict:
    result =await manuals_client.search(
        query = arguments["query"],
        machine_id=arguments["machine_id"],
    )

    return{
        "answer": result.answer,
        "citations": [c.model_dump() for c in result.citations],
        "confidence": result.confidence,
    }


AGENT_TOOLS: list[AgentTool]=[
    AgentTool(
        name="search_manuals",
        description = ("Search the use and maintenance manuals of a specific machine. "
                        "Use it when the user asks how to operate, configure or "
                        "troubleshoot a machine, based on the official "
                        "documentation (error codes, procedures, settings, safety)."),
        parameters={
            "type": "object", 
            "properties":{
                "query": {
                    "type": "string",
                    "description": "The user's question riformulate as query"
                }, 
                "machine_id":{
                    "type": "string",
                    "description": "The identifier of the machine the question refers to"
                },
            },
            "required": ["query", "machine_id"],
        },
        handler=_handle_search_manuals, 
    ),

]


 
def as_llm_tool_defs() -> list[dict]:
    """Converts AGENT_TOOLS into the tool-schema format expected by the LLM adapter."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in AGENT_TOOLS
    ]
 
 
def get_tool_by_name(name: str) -> AgentTool | None:
    return next((t for t in AGENT_TOOLS if t.name == name), None)