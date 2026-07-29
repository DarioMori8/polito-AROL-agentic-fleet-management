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


_MACHINES: list[Machine] = [
    Machine(id="1", name="Capping Line Alpha", model="AROL EURO PK",
            serial_number="AR-EPK-2021-0453", status=MachineStatus.ONLINE,
            location="Bottling Line 1"),
    Machine(id="2", name="Capping Line Bravo", model="AROL EQUATORQUE",
            serial_number="AR-EQT-2022-0817", status=MachineStatus.ONLINE,
            location="Bottling Line 2"),
    Machine(id="3", name="Capping Line Charlie", model="AROL EURO VP",
            serial_number="AR-EVP-2023-0129", status=MachineStatus.MAINTENANCE,
            location="Bottling Line 3"),
]


_MANUALS: list[Manual] = [
    Manual(id="man_1", machine_id="1", title="Use & Maintenance Manual",
           filename="euro_pk_use_maintenance.pdf", language="en",
           page_count=142, url="/static/manuals/euro_pk_use_maintenance.pdf"),
    Manual(id="man_2", machine_id="2", title="Use & Maintenance Manual",
           filename="manual_1.pdf", language="en",
           page_count=98, url="/static/manuals/manual_1.pdf"),
    Manual(id="man_3", machine_id="2", title="Quick Start Guide",
           filename="equatorque_quickstart.pdf", language="it",
           page_count=24, url="/static/manuals/equatorque_quickstart.pdf"),
    Manual(id="man_4", machine_id="3", title="Use & Maintenance Manual",
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