from typing import Any, Literal

from pydantic import BaseModel, Field


class SearchIoTTask(BaseModel):
    """Request sent to the IoT Agent for one machine's operational data."""

    query: str
    machine_id: str


class IoTObservation(BaseModel):
    """Structured backoffice result used to support the agent's answer."""

    kind: Literal["health", "telemetry", "alarms", "maintenance"]
    data: dict[str, Any]


class SearchIoTResponse(BaseModel):
    """Answer plus the exact operational records/aggregates consulted."""

    answer: str
    observations: list[IoTObservation] = Field(default_factory=list)
    confidence: float
