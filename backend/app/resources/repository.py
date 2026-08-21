from abc import ABC, abstractmethod

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.models import Machine, Manual


# --- Interfaces ---

class MachineRepository(ABC):
    @abstractmethod
    async def list_machines(self) -> list[Machine]: ...

    @abstractmethod
    async def get_machine(self, machine_id: str) -> Machine | None: ...

    @abstractmethod
    async def get_machine_by_serial(self, serial_number: str) -> Machine | None: ...


class ManualRepository(ABC):
    @abstractmethod
    async def get_by_machine(self, machine_id: str) -> Manual | None: ...

    @abstractmethod
    async def get_by_filename(self, filename: str) -> Manual | None: ...

    @abstractmethod
    async def get_manual(self, manual_id: str) -> Manual | None: ...



class DbMachineRepository(MachineRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_machines(self) -> list[Machine]:
        # returns the whole fleet, across every company. ù
        result = await self._session.exec(select(Machine))
        return list(result.all())

    async def get_machine(self, machine_id: str) -> Machine | None:
        return await self._session.get(Machine, machine_id)

    async def get_machine_by_serial(self, serial_number: str) -> Machine | None:
        # The other half of the "two identifiers" story: the serial number is
        # what arrives from outside (a QR code, a manual filename, an operator
        # reading the plate), and this is where it becomes a machine_id.
        result = await self._session.exec(
            select(Machine).where(Machine.serial_number == serial_number)
        )
        return result.one_or_none()


class DbManualRepository(ManualRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_machine(self, machine_id: str) -> Manual | None:
        # Singular, not a list: manuals.machine_id is UNIQUE, so a machine has
        # at most one manual. Returning a list here would advertise a
        # cardinality the schema forbids.
        result = await self._session.exec(
            select(Manual).where(Manual.machine_id == machine_id)
        )
        return result.one_or_none()

    async def get_by_filename(self, filename: str) -> Manual | None:
        # Entry point for citations coming back from the agents service: the
        # agent cites a source file, the backend turns that string into a row
        # (and from there into a machine) so the frontend can link to it.
        result = await self._session.exec(
            select(Manual).where(Manual.filename == filename)
        )
        return result.first()

    async def get_manual(self, manual_id: str) -> Manual | None:
        return await self._session.get(Manual, manual_id)