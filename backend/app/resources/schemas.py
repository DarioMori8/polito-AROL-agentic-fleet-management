# resources/schemas.py
from enum import Enum
from pydantic import BaseModel


class MachineStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class Machine(BaseModel):
    id: str
    name: str
    model: str          # real AROL model string (e.g. "AROL EQUATORQUE")
    serial_number: str
    company_id: str     # owning customer: the tenant boundary for every lookup
    status: MachineStatus  # runtime state
    location: str   #e.g. "Bottling Line 2"


class Manual(BaseModel):
    id: str
    machine_id: str
    title: str
    filename: str
    language: str
    page_count: int
    url: str