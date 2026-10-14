from datetime import datetime

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


def _parse_iso(value) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=None)


class IoTAgent(BaseAgent):
    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    @property
    def tools(self) -> list[dict]:
        return TOOLS

    async def run(self, task: SearchIoTTask) -> SearchIoTResponse:
        self._task = task
        self._latest_snapshot: datetime | None = None
        self._latest_snapshot_loaded = False
        return await super().run(task)

    def _user_message(self, task: SearchIoTTask) -> str:
        return task.query

    async def _execute_tool(self, tool_call: ToolCall) -> dict:
        args = tool_call.arguments
        client = get_iot_client()
        # The machine id comes from trusted request context. It is deliberately
        # absent from every LLM-facing tool schema, so the model cannot cross it.
        machine_id = self._task.machine_id
        args, note = await self._guard_explicit_bounds(client, tool_call.name, args)

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

        result = {"tool": tool_call.name, "data": data}
        if note:
            result["note"] = note
        return result

    async def _guard_explicit_bounds(
        self, client, tool_name: str, args: dict
    ) -> tuple[dict, str | None]:
        """Drop explicit bounds that start after the newest dataset snapshot.

        The model sees the wall-clock date (the Ollama chat template injects
        it) and sometimes turns "today" or "recent" into absolute dates. The
        synthetic dataset ended earlier, so such a range is always empty and
        would be reported as "no data". Falling back to the rolling window,
        which the backoffice anchors to the newest snapshot, answers the
        question that was actually asked.
        """
        start_key, end_key = (
            ("from_date", "to_date")
            if tool_name == "search_maintenance"
            else ("from_timestamp", "to_timestamp")
        )
        start = _parse_iso(args.get(start_key))
        if start is None:
            return args, None
        latest = await self._latest_snapshot_for(client)
        if latest is None or start <= latest:
            return args, None
        guarded = {k: v for k, v in args.items() if k not in (start_key, end_key)}
        return guarded, (
            f"Requested range starting {args.get(start_key)} is after the newest "
            f"snapshot in the dataset ({latest.isoformat(timespec='minutes')}); "
            "ignored it and used the rolling window ending at that snapshot."
        )

    async def _latest_snapshot_for(self, client) -> datetime | None:
        if not self._latest_snapshot_loaded:
            self._latest_snapshot_loaded = True
            try:
                health = await client.get_health(
                    machine_id=self._task.machine_id, window_hours=1
                )
                self._latest_snapshot = _parse_iso(health["window"]["to"])
            except Exception:
                # Without the anchor, keep the model's bounds rather than
                # failing the tool call.
                self._latest_snapshot = None
        return self._latest_snapshot

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
