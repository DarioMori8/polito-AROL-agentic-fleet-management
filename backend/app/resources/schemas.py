# resources/schemas.py
from enum import Enum
from pydantic import BaseModel


class MachineType(str, Enum):
    CAPPING = "capping"
    FILLING = "filling"
    INSPECTION = "inspection"


class MachineStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class Machine(BaseModel):
    id: str
    name: str
    model: str
    serial_number: str
    type: MachineType
    status: MachineStatus


