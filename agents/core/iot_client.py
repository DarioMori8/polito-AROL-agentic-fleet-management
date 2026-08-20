import httpx

from core.config import settings


OPERATIONAL_STATUSES = (
    "Running",
    "Alarm",
    "Idle",
    "Stopped",
    "Maintenance",
    "Size change",
)
ALARM_SEVERITIES = ("Critical", "High", "Medium", "Low")
ALARM_STATUSES = ("Open", "Acknowledged", "Resolved")
TICKET_STATUSES = ("Open", "In progress", "Waiting for parts", "Resolved", "Closed")
TICKET_PRIORITIES = ("Critical", "High", "Medium", "Low")


def _canonical(value: str | None, vocabulary: tuple[str, ...]) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    key = value.lower().replace("_", " ")
    for term in vocabulary:
        if term.lower() == key:
            return term
    # Keep an unknown value so the strict backoffice rejects it. Silently
    # dropping it would widen a query chosen by the model.
    return value


def _clean_params(params: dict) -> dict:
    """Drop optional values that an LLM expressed as blank strings."""
    cleaned = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue
        cleaned[key] = value
    return cleaned


class IoTClient:
    """HTTP seam between the IoT Agent and the operational data service."""

    def __init__(self):
        self.base_url = settings.IOT_SERVICE_URL

    async def get_health(self, machine_id: str, window_hours: int) -> dict:
        return await self._get(
            f"/machines/{machine_id}/health", {"window_hours": window_hours}
        )

    async def search_telemetry(
        self,
        machine_id: str,
        window_hours: int | None = None,
        from_timestamp: str | None = None,
        to_timestamp: str | None = None,
        operational_status: str | None = None,
        limit: int = 24,
    ) -> dict:
        return await self._get(
            f"/machines/{machine_id}/telemetry",
            {
                "window_hours": window_hours,
                "from_timestamp": from_timestamp,
                "to_timestamp": to_timestamp,
                "operational_status": _canonical(
                    operational_status, OPERATIONAL_STATUSES
                ),
                "limit": limit,
            },
        )

    async def search_alarms(
        self,
        machine_id: str,
        window_hours: int | None = None,
        from_timestamp: str | None = None,
        to_timestamp: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        alarm_code: str | None = None,
        limit: int = 50,
    ) -> dict:
        return await self._get(
            f"/machines/{machine_id}/alarms",
            {
                "window_hours": window_hours,
                "from_timestamp": from_timestamp,
                "to_timestamp": to_timestamp,
                "severity": _canonical(severity, ALARM_SEVERITIES),
                "status": _canonical(status, ALARM_STATUSES),
                "alarm_code": alarm_code,
                "limit": limit,
            },
        )

    async def search_maintenance(
        self,
        machine_id: str,
        from_date: str | None = None,
        to_date: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        alarm_id: str | None = None,
        limit: int = 50,
    ) -> dict:
        return await self._get(
            f"/machines/{machine_id}/maintenance-tickets",
            {
                "from_date": from_date,
                "to_date": to_date,
                "status": _canonical(status, TICKET_STATUSES),
                "priority": _canonical(priority, TICKET_PRIORITIES),
                "alarm_id": alarm_id,
                "limit": limit,
            },
        )

    async def _get(self, path: str, params: dict) -> dict:
        params = _clean_params(params)
        async with httpx.AsyncClient(base_url=self.base_url, timeout=20.0) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()


_client: IoTClient | None = None


def get_iot_client() -> IoTClient:
    global _client
    if _client is None:
        _client = IoTClient()
    return _client
