from abc import ABC, abstractmethod

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.models import Machine, Manual


# Every repository here is TENANT-SCOPED: it is built for one company and can
# only ever see that company's rows. company_id is fixed at construction time,
# taken from the authenticated user by the dependency provider, and never from
# the client. There is deliberately no method that bypasses the scope, so a
# new query cannot "forget" the tenant filter: the filter is part of the
# object, not of each call.
#
# A row belonging to another company is indistinguishable from a row that
# does not exist: both come back as None, which the router turns into 404.
# Answering 403 instead would confirm to the caller that the id exists.


# --- Interfaces

class MachineRepository(ABC):
    @abstractmethod
    async def list_all(self) -> list[Machine]: ...

    @abstractmethod
    async def get(self, machine_id: str) -> Machine | None: ...

    @abstractmethod
    async def get_by_serial(self, serial_number: str) -> Machine | None: ...


class ManualRepository(ABC):
    @abstractmethod
    async def get(self, manual_id: str) -> Manual | None: ...

    @abstractmethod
    async def get_by_machine(self, machine_id: str) -> Manual | None: ...

    @abstractmethod
    async def get_by_filename(self, filename: str) -> Manual | None: ...


# --- SQL implementations

class DbMachineRepository(MachineRepository):
    def __init__(self, session: AsyncSession, company_id: str):
        self._session = session
        self._company_id = company_id

    def _scoped(self):
        # Base query every method starts from: machines of this company only.
        return select(Machine).where(Machine.company_id == self._company_id)

    async def list_all(self) -> list[Machine]:
        # Explicit ORDER BY: without it SQL guarantees no order, and the
        # frontend list could reshuffle between two identical calls.
        result = await self._session.exec(self._scoped().order_by(Machine.id))
        return list(result.all())

    async def get(self, machine_id: str) -> Machine | None:
        # Not session.get(): a primary-key lookup cannot carry the tenant
        # condition, and would return another company's machine.
        result = await self._session.exec(
            self._scoped().where(Machine.id == machine_id)
        )
        return result.one_or_none()

    async def get_by_serial(self, serial_number: str) -> Machine | None:
        # The other half of the "two identifiers" story: the serial number is
        # what arrives from outside (a QR code, a manual filename, an operator
        # reading the plate), and this is where it becomes a machine_id.
        # serial_number is UNIQUE, so one_or_none(): more than one row would
        # be a broken invariant and must fail loudly, not be papered over.
        result = await self._session.exec(
            self._scoped().where(Machine.serial_number == serial_number)
        )
        return result.one_or_none()


class DbManualRepository(ManualRepository):
    def __init__(self, session: AsyncSession, company_id: str):
        self._session = session
        self._company_id = company_id

    def _scoped(self):
        # manuals has no company_id of its own: ownership is inherited from
        # the machine the manual belongs to, hence the join.
        return (
            select(Manual)
            .join(Machine, Manual.machine_id == Machine.id)
            .where(Machine.company_id == self._company_id)
        )

    async def get(self, manual_id: str) -> Manual | None:
        result = await self._session.exec(
            self._scoped().where(Manual.id == manual_id)
        )
        return result.one_or_none()

    async def get_by_machine(self, machine_id: str) -> Manual | None:
        # Singular, not a list: manuals.machine_id is UNIQUE, so a machine has
        # at most one manual. Returning a list here would advertise a
        # cardinality the schema forbids.
        result = await self._session.exec(
            self._scoped().where(Manual.machine_id == machine_id)
        )
        return result.one_or_none()

    async def get_by_filename(self, filename: str) -> Manual | None:
        # Entry point for citations coming back from the agents service: the
        # agent cites a source file, the backend turns that string into a row
        # (and from there into a machine) so the frontend can link to it.
        # filename is UNIQUE, so one_or_none() like every other single lookup.
        result = await self._session.exec(
            self._scoped().where(Manual.filename == filename)
        )
        return result.one_or_none()
