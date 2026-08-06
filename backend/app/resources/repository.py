# resources/repository.py
from abc import ABC, abstractmethod

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.models import Machine, Document, DocumentType


# --- Interfaces ---

class MachineRepository(ABC):
    @abstractmethod
    async def list_machines(self) -> list[Machine]: ...

    @abstractmethod
    async def get_machine(self, machine_id: str) -> Machine | None: ...


class DocumentRepository(ABC):
    @abstractmethod
    async def list_by_machine(
        self, machine_id: str, document_type: DocumentType | None = None
    ) -> list[Document]: ...

    @abstractmethod
    async def get_document(self, document_id: str) -> Document | None: ...


# --- DB-backed implementations ---

class DbMachineRepository(MachineRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_machines(self) -> list[Machine]:
        result = await self._session.exec(select(Machine))
        return list(result.all())

    async def get_machine(self, machine_id: str) -> Machine | None:
        return await self._session.get(Machine, machine_id)


class DbDocumentRepository(DocumentRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_by_machine(
        self, machine_id: str, document_type: DocumentType | None = None
    ) -> list[Document]:
        statement = select(Document).where(Document.machine_id == machine_id)
        # Optional type filter: callers wanting only manuals pass
        # document_type=DocumentType.MANUAL; callers wanting everything omit it.
        if document_type is not None:
            statement = statement.where(Document.document_type == document_type)
        result = await self._session.exec(statement)
        return list(result.all())

    async def get_document(self, document_id: str) -> Document | None:
        return await self._session.get(Document, document_id)