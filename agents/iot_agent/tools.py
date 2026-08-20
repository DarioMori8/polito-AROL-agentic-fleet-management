ANALYZE_HEALTH_TOOL = {
    "type": "function",
    "function": {
        "name": "analyze_machine_health",
        "description": (
            "Get a compact operational overview for this machine over a rolling number "
            "of hours: newest snapshot, uptime, production, temperatures, energy, status "
            "distribution, alarm totals and top alarm codes. Prefer this for broad health, "
            "performance, current-state or trend questions. The window ends at the newest "
            "snapshot in the dataset, not at wall-clock time."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "window_hours": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 720,
                    "description": "Rolling analysis window. Use 24 for a day, 168 for a week, 720 for the full month.",
                }
            },
            "required": ["window_hours"],
        },
    },
}

SEARCH_TELEMETRY_TOOL = {
    "type": "function",
    "function": {
        "name": "search_telemetry",
        "description": (
            "Search individual hourly IoT snapshots and aggregates for the same filter. "
            "Use it for a specific time/status or when individual readings are needed; use "
            "analyze_machine_health for a broad overview. Explicit ISO dates override the "
            "rolling window. Results are newest first."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "window_hours": {"type": "integer", "minimum": 1, "maximum": 720},
                "from_timestamp": {"type": "string", "description": "ISO-8601 lower bound, e.g. 2026-08-04T08:00"},
                "to_timestamp": {"type": "string", "description": "ISO-8601 upper bound; a date includes that whole day"},
                "operational_status": {
                    "type": "string",
                    "enum": ["Running", "Alarm", "Idle", "Stopped", "Maintenance", "Size change"],
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 48},
            },
            "required": [],
        },
    },
}

SEARCH_ALARMS_TOOL = {
    "type": "function",
    "function": {
        "name": "search_alarms",
        "description": (
            "Search alarm events for this machine. It returns matching totals, breakdowns "
            "and bounded event rows. Use it for active alarms, severity, alarm history or a "
            "specific ALnnn code. Explicit ISO dates override the rolling window."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "window_hours": {"type": "integer", "minimum": 1, "maximum": 720},
                "from_timestamp": {"type": "string"},
                "to_timestamp": {"type": "string"},
                "severity": {"type": "string", "enum": ["Critical", "High", "Medium", "Low"]},
                "status": {"type": "string", "enum": ["Open", "Acknowledged", "Resolved"]},
                "alarm_code": {"type": "string", "description": "Exact alarm code, e.g. AL031_HEADS_MOTOR_OVERLOAD"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "required": [],
        },
    },
}

SEARCH_MAINTENANCE_TOOL = {
    "type": "function",
    "function": {
        "name": "search_maintenance",
        "description": (
            "Search maintenance/service tickets for this machine, including tickets not "
            "originated by an alarm. Use it for interventions, open work, responsibility, "
            "priority, or to find the ticket linked to an alarm event."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "from_date": {"type": "string", "description": "ISO date lower bound"},
                "to_date": {"type": "string", "description": "ISO date upper bound"},
                "status": {"type": "string", "enum": ["Open", "In progress", "Waiting for parts", "Resolved", "Closed"]},
                "priority": {"type": "string", "enum": ["Critical", "High", "Medium", "Low"]},
                "alarm_id": {"type": "string", "description": "Exact event id, e.g. ALM-0228 (not the ALnnn alarm code)"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "required": [],
        },
    },
}

ANALYZE_ALARM_TICKET_COVERAGE_TOOL = {
    "type": "function",
    "function": {
        "name": "analyze_alarm_ticket_coverage",
        "description": (
            "Correlate alarm events with maintenance tickets for this machine. Returns "
            "which matching alarms have one or more linked tickets, which have none, and "
            "the status, priority and owner role of each linked ticket. Prefer this when "
            "the user asks whether alarms are already being handled or need a ticket."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "window_hours": {"type": "integer", "minimum": 1, "maximum": 720},
                "from_timestamp": {"type": "string"},
                "to_timestamp": {"type": "string"},
                "severity": {
                    "type": "string",
                    "enum": ["Critical", "High", "Medium", "Low"],
                },
                "status": {
                    "type": "string",
                    "enum": ["Open", "Acknowledged", "Resolved"],
                    "description": "Alarm status. Use Open when asking what still needs attention.",
                },
                "alarm_code": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "required": [],
        },
    },
}

TOOLS = [
    ANALYZE_HEALTH_TOOL,
    SEARCH_TELEMETRY_TOOL,
    SEARCH_ALARMS_TOOL,
    SEARCH_MAINTENANCE_TOOL,
    ANALYZE_ALARM_TICKET_COVERAGE_TOOL,
]
