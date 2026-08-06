# resources/router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from app.db.engine import get_session

from app.resources.repository import (MachineRepository, DocumentRepository, DbDocumentRepository, DbMachineRepository)
from app.db.models import Machine, Document, DocumentType

router = APIRouter(prefix="/v1", tags=["resources"])


# The single swap point: when the real DB arrives, return the DB-backed
# implementation here and nothing else in the codebase changes.
def get_machine_repository(
    session: AsyncSession = Depends(get_session),
) -> MachineRepository:
    return DbMachineRepository(session)

def get_document_repository(
    session: AsyncSession = Depends(get_session),
) -> DocumentRepository:
    return DbDocumentRepository(session)

@router.get("/machines", response_model=list[Machine])
async def list_machines(
    repo: MachineRepository = Depends(get_machine_repository),
) -> list[Machine]:
    return await repo.list_machines()


@router.get("/machines/{machine_id}", response_model=Machine)
async def get_machine(
    machine_id: str,
    repo: MachineRepository = Depends(get_machine_repository),
) -> Machine:
    machine = await repo.get_machine(machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail=f"Machine '{machine_id}' not found")
    return machine


# --- Document (manual) endpoints ---

@router.get("/machines/{machine_id}/manuals", response_model=list[Document])
async def list_machine_manuals(
    machine_id: str,
    machine_repo: MachineRepository = Depends(get_machine_repository),
    document_repo: DocumentRepository = Depends(get_document_repository),
) -> list[Document]:
    if await machine_repo.get_machine(machine_id) is None:
        raise HTTPException(status_code=404, detail=f"Machine '{machine_id}' not found")
    return await document_repo.list_by_machine(machine_id, document_type=DocumentType.MANUAL)


@router.get("/manuals/{manual_id}", response_model=Document)
async def get_manual(
    manual_id: str,
    document_repo: DocumentRepository = Depends(get_document_repository),
) -> Document:
    doc = await document_repo.get_document(manual_id)
    if doc is None or doc.document_type != DocumentType.MANUAL:
        raise HTTPException(status_code=404, detail=f"Manual '{manual_id}' not found")
    return doc