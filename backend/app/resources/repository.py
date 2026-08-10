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


# The real fleet from the Q2 dataset, transcribed. `id` is the dataset's
# machineId, which is the single identifier the whole platform speaks: it travels
# from the QR code through the chat request down to the metadata of the manual
# chunks in Chroma, unchanged at every hop. The serial number stays what it is in
# reality, an attribute of the machine — the one the manual file is named after.
#
# `status` has no equivalent in the dataset: there it is derived from the latest
# telemetry snapshot, so the values below are the one thing here still made up.
# This whole list is meant to be replaced by a call to the backoffice's
# GET /machines, which already returns exactly these rows.
_MACHINES: list[Machine] = [
    Machine(id="MCH-0001", name="Novara Line 3", model="TS-EURO-PK-TWIN-CHUTE-D",
            serial_number="15610",
            company_id="CMP-001", status=MachineStatus.ONLINE,
            location="Novara Plant 1 - Bottling Line 3"),
    Machine(id="MCH-0002", name="Novara Line 5", model="TSI-EURO-VA-IES-LIGHT",
            serial_number="17203",
            company_id="CMP-001", status=MachineStatus.ONLINE,
            location="Novara Plant 1 - Bottling Line 5"),
    Machine(id="MCH-0003", name="Alessandria Line 1", model="TSI-EURO-VA-IES-LIGHT",
            serial_number="17579",
            company_id="CMP-001", status=MachineStatus.MAINTENANCE,
            location="Alessandria Plant 2 - Bottling Line 1"),
    Machine(id="MCH-0004", name="Zaragoza Suite B", model="M-EURO-VP-IES",
            serial_number="17478",
            company_id="CMP-003", status=MachineStatus.ONLINE,
            location="Zaragoza Plant 1 - Filling Suite B"),
    Machine(id="MCH-0005", name="Zaragoza Suite A", model="TSI-CLOSYS-EAGLE-PK",
            serial_number="A4344",
            company_id="CMP-003", status=MachineStatus.ONLINE,
            location="Zaragoza Plant 1 - Filling Suite A"),
    Machine(id="MCH-0006", name="Glasgow Line 2", model="EAGLE-PK-TURRET",
            serial_number="A2064",
            company_id="CMP-004", status=MachineStatus.ONLINE,
            location="Glasgow Plant 1 - Line 2"),
    Machine(id="MCH-0007", name="Saintes Hall A", model="EAGLE-VA-TURRET",
            serial_number="A2055",
            company_id="CMP-002", status=MachineStatus.ONLINE,
            location="Saintes Plant 1 - Bottling Hall A"),
    Machine(id="MCH-0008", name="Saintes Hall B", model="EAGLE-VA-TURRET",
            serial_number="A2132",
            company_id="CMP-002", status=MachineStatus.OFFLINE,
            location="Saintes Plant 1 - Bottling Hall B"),
]


# One manual per machine, named after the serial number — the real files, the
# same ones the ingestion indexes. `url` is still a promise: no endpoint serves
# these PDFs yet, and when one does it will have to check who is asking.
_MANUALS: list[Manual] = [
    Manual(id=f"man_{machine.id}", machine_id=machine.id,
           title="Use & Maintenance Manual",
           filename=f"{machine.serial_number}_manual_EN.pdf", language="EN",
           page_count=page_count,
           url=f"/static/manuals/{machine.serial_number}_manual_EN.pdf")
    for machine, page_count in zip(
        _MACHINES, [155, 147, 142, 261, 157, 114, 100, 82]
    )
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