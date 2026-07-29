# resources/repository.py
from abc import ABC, abstractmethod

from app.resources.schemas import Machine,  MachineStatus


class MachineRepository(ABC):
    @abstractmethod
    async def list_machines(self) -> list[Machine]: ...

    @abstractmethod
    async def get_machine(self, machine_id: str) -> Machine | None: ...



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




class InMemoryMachineRepository(MachineRepository):
    async def list_machines(self) -> list[Machine]:
        return list(_MACHINES)

    async def get_machine(self, machine_id: str) -> Machine | None:
        return next((m for m in _MACHINES if m.id == machine_id), None)