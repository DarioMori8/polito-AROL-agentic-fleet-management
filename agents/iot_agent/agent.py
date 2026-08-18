from contracts import IoTObservation, SearchIoTResponse, SearchIoTTask

from core.base_agent import BaseAgent
from core.iot_client import get_iot_client
from core.llm_adapter import LLMResponse, ToolCall
from iot_agent.prompts import SYSTEM_PROMPT
from iot_agent.tools import TOOLS


KIND_BY_TOOL = {
    "analyze_machine_health": "health",
    "search_telemetry": "telemetry",
    "search_alarms": "alarms",
    "search_maintenance": "maintenance",
    "analyze_alarm_ticket_coverage": "alarms",
}


def _bounded_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))


class IoTAgent(BaseAgent):
    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    @property
    def tools(self) -> list[dict]:
        return TOOLS

    async def run(self, task: SearchIoTTask) -> SearchIoTResponse:
        self._task = task
        return await super().run(task)

    def _user_message(self, task: SearchIoTTask) -> str:
        return task.query

    async def _execute_tool(self, tool_call: ToolCall) -> dict:
        args = tool_call.arguments
        client = get_iot_client()
        # The machine id comes from trusted request context. It is deliberately
        # absent from every LLM-facing tool schema, so the model cannot cross it.
        machine_id = self._task.machine_id

        if tool_call.name == "analyze_machine_health":
            data = await client.get_health(
                machine_id=machine_id,
                window_hours=_bounded_int(args.get("window_hours"), 24, 1, 720),
            )
        elif tool_call.name == "search_telemetry":
            data = await client.search_telemetry(
                machine_id=machine_id,
                window_hours=_bounded_int(args.get("window_hours"), 24, 1, 720),
                from_timestamp=args.get("from_timestamp"),
                to_timestamp=args.get("to_timestamp"),
                operational_status=args.get("operational_status"),
                limit=_bounded_int(args.get("limit"), 24, 1, 48),
            )
        elif tool_call.name == "search_alarms":
            data = await client.search_alarms(
                machine_id=machine_id,
                window_hours=_bounded_int(args.get("window_hours"), 168, 1, 720),
                from_timestamp=args.get("from_timestamp"),
                to_timestamp=args.get("to_timestamp"),
                severity=args.get("severity"),
                status=args.get("status"),
                alarm_code=args.get("alarm_code"),
                limit=_bounded_int(args.get("limit"), 50, 1, 50),
            )
        elif tool_call.name == "search_maintenance":
            data = await client.search_maintenance(
                machine_id=machine_id,
                from_date=args.get("from_date"),
                to_date=args.get("to_date"),
                status=args.get("status"),
                priority=args.get("priority"),
                alarm_id=args.get("alarm_id"),
                limit=_bounded_int(args.get("limit"), 50, 1, 50),
            )
        elif tool_call.name == "analyze_alarm_ticket_coverage":
            data = await self._analyze_alarm_ticket_coverage(client, args, machine_id)
        else:
            return {"error": f"unknown tool: {tool_call.name}"}

        return {"tool": tool_call.name, "data": data}

    async def _analyze_alarm_ticket_coverage(
        self, client, args: dict, machine_id: str
    ) -> dict:
        """Join alarm events to tickets without asking the LLM to correlate ids."""
        alarms = await client.search_alarms(
            machine_id=machine_id,
            window_hours=_bounded_int(args.get("window_hours"), 168, 1, 720),
            from_timestamp=args.get("from_timestamp"),
            to_timestamp=args.get("to_timestamp"),
            severity=args.get("severity"),
            status=args.get("status"),
            alarm_code=args.get("alarm_code"),
            limit=_bounded_int(args.get("limit"), 50, 1, 50),
        )
        tickets = await client.search_maintenance(machine_id=machine_id, limit=50)

        tickets_by_alarm: dict[str, list[dict]] = {}
        for ticket in tickets.get("results", []):
            alarm_id = ticket.get("alarm_id")
            if alarm_id:
                tickets_by_alarm.setdefault(alarm_id, []).append(ticket)

        correlated = []
        with_ticket = 0
        for alarm in alarms.get("results", []):
            linked_tickets = tickets_by_alarm.get(alarm.get("alarm_id"), [])
            has_ticket = bool(linked_tickets)
            with_ticket += int(has_ticket)
            correlated.append(
                {
                    **alarm,
                    "has_ticket": has_ticket,
                    "tickets": linked_tickets,
                }
            )

        returned_alarms = len(correlated)
        matched_tickets = tickets.get("summary", {}).get("matched_tickets", 0)
        returned_tickets = len(tickets.get("results", []))
        return {
            "machine_id": machine_id,
            "window": alarms.get("window"),
            "filters": alarms.get("filters", {}),
            "summary": {
                "matched_alarms": alarms.get("summary", {}).get(
                    "matched_alarms", returned_alarms
                ),
                "returned_alarms": returned_alarms,
                "with_ticket": with_ticket,
                "without_ticket": returned_alarms - with_ticket,
                "ticket_scan_complete": matched_tickets <= returned_tickets,
            },
            "alarms": correlated,
        }

    def _build_response(
        self, final: LLMResponse, tool_results: list[dict]
    ) -> SearchIoTResponse:
        observations = [
            IoTObservation(kind=KIND_BY_TOOL[result["tool"]], data=result["data"])
            for result in tool_results
            if result.get("tool") in KIND_BY_TOOL and isinstance(result.get("data"), dict)
        ]
        return SearchIoTResponse(
            answer=final.content or "",
            observations=observations,
            confidence=1.0 if observations else 0.0,
        )
