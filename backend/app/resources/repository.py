# resources/repository.py
from abc import ABC, abstractmethod

from app.resources.schemas import Machine,  MachineStatus, Manual


class MachineRepository(ABC):
    @abstractmethod
    async def list_machines(self) -> list[Machine]: ...

    @abstractmethod
    async def get_machine(self, machine_id: str) -> Machine | None: ...

class ManualRepository(ABC):
    @abstractmethod
    async def list_by_machine(self, machine_id: str)-> list[Manual]:
        ...

    @abstractmethod
    async def get_manual(self, manual_id: str)-> Manual | None:
        ...

# --- Mock data (the first implementation of the interfaces, not throwaway) ---


# The ids are the identifiers the manuals are indexed under in Chroma, taken
# from the manual file names (17478_manual_EN.pdf -> 17478). Keeping them here
# means the id travelling from the QR code down to the vector store is the same
# string at every hop, with no translation layer in between. Everything else in
# this mock is still placeholder, waiting for AROL_Q2_synthetic_fleet_dataset.xlsx.
_MACHINES: list[Machine] = [
    Machine(id="17478", name="Capping Line Alpha", model="AROL EURO PK",
            serial_number="17478", status=MachineStatus.ONLINE,
            location="Bottling Line 1"),
    Machine(id="15610", name="Capping Line Bravo", model="AROL EQUATORQUE",
            serial_number="15610", status=MachineStatus.ONLINE,
            location="Bottling Line 2"),
    Machine(id="A2055", name="Capping Line Charlie", model="AROL EURO VP",
            serial_number="A2055", status=MachineStatus.MAINTENANCE,
            location="Bottling Line 3"),
]


# machine_id realigned to the ids above; file names, page counts and urls are
# still placeholder — no endpoint serves these files yet.
_MANUALS: list[Manual] = [
    Manual(id="man_1", machine_id="17478", title="Use & Maintenance Manual",
           filename="euro_pk_use_maintenance.pdf", language="en",
           page_count=142, url="/static/manuals/euro_pk_use_maintenance.pdf"),
    Manual(id="man_2", machine_id="15610", title="Use & Maintenance Manual",
           filename="manual_1.pdf", language="en",
           page_count=98, url="/static/manuals/manual_1.pdf"),
    Manual(id="man_3", machine_id="15610", title="Quick Start Guide",
           filename="equatorque_quickstart.pdf", language="it",
           page_count=24, url="/static/manuals/equatorque_quickstart.pdf"),
    Manual(id="man_4", machine_id="A2055", title="Use & Maintenance Manual",
           filename="euro_vp_use_maintenance.pdf", language="en",
           page_count=67, url="/static/manuals/euro_vp_use_maintenance.pdf"),
]




class InMemoryMachineRepository(MachineRepository):
    async def list_machines(self) -> list[Machine]:
        return list(_MACHINES)

    async def get_machine(self, machine_id: str) -> Machine | None:
        return next((m for m in _MACHINES if m.id == machine_id), None)
    

class InMemoryManualRepository(ManualRepository):
    async def list_by_machine(self, machine_id: str)-> list[Manual]:
        return [m for m in _MANUALS if m.machine_id == machine_id]

    async def get_manual(self, manual_id: str)-> Manual|None:
        return next((m for m in _MANUALS if m.id==manual_id), None)