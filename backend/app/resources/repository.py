# resources/repository.py
from abc import ABC, abstractmethod

from resources.schemas import Machine, MachineType, MachineStatus


class MachineRepository(ABC):
    @abstractmethod
    async def list_machines(self) -> list[Machine]: ...

    @abstractmethod
    async def get_machine(self, machine_id: str) -> Machine | None: ...



# --- Mock data (the first implementation of the interfaces, not throwaway) ---

_MACHINES: list[Machine] = [
    Machine(id="1", name="Capping Line Alpha", model="AROL EQUATORQUE 18",
            serial_number="AR-EQ-2021-0453", type=MachineType.CAPPING,
            status=MachineStatus.ONLINE),
    Machine(id="2", name="Capping Line Bravo", model="AROL EQUATORQUE 24",
            serial_number="AR-EQ-2022-0817", type=MachineType.CAPPING,
            status=MachineStatus.ONLINE),
    Machine(id="3", name="Inspection Unit Charlie", model="AROL VISIONCHECK 4",
            serial_number="AR-VC-2023-0129", type=MachineType.INSPECTION,
            status=MachineStatus.MAINTENANCE),
]




class InMemoryMachineRepository(MachineRepository):
    async def list_machines(self) -> list[Machine]:
        return list(_MACHINES)

    async def get_machine(self, machine_id: str) -> Machine | None:
        return next((m for m in _MACHINES if m.id == machine_id), None)