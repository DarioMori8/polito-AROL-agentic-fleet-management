
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.engine import get_session
from app.resources.repository import (
    DbMachineRepository,
    DbManualRepository,
    MachineRepository,
    ManualRepository,
)
from app.resources.schemas import MachineOut, ManualOut

router = APIRouter(prefix="/v1", tags=["resources"])


# --- Dependency providers 


def get_machine_repository(
    session: AsyncSession = Depends(get_session),
) -> MachineRepository:
    return DbMachineRepository(session)


def get_manual_repository(
    session: AsyncSession = Depends(get_session),
) -> ManualRepository:
    return DbManualRepository(session)


# --- Machine endpoints 

@router.get("/machines", response_model=list[MachineOut])
async def list_machines(
    repo: MachineRepository = Depends(get_machine_repository),
) -> list[MachineOut]:
    # NOTE: no tenant filter yet. This returns every company's fleet and must
    # take company_id from the authenticated user once auth exists.
    machines = await repo.list_machines()
    return [MachineOut.from_model(m) for m in machines]


@router.get("/machines/{machine_id}", response_model=MachineOut)
async def get_machine(
    machine_id: str,
    repo: MachineRepository = Depends(get_machine_repository),
) -> MachineOut:
    machine = await repo.get_machine(machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail=f"Machine '{machine_id}' not found")
    return MachineOut.from_model(machine)


@router.get("/machines/by-serial/{serial_number}", response_model=MachineOut)
async def get_machine_by_serial(
    serial_number: str,
    repo: MachineRepository = Depends(get_machine_repository),
) -> MachineOut:
    """
    Lookup by the identifier printed on the machine. The README's QR scheme
    allows either form of URL, and a citation coming back from the agents
    carries a serial too, so both paths land here.
    """
    machine = await repo.get_machine_by_serial(serial_number)
    if machine is None:
        raise HTTPException(
            status_code=404, detail=f"No machine with serial '{serial_number}'"
        )
    return MachineOut.from_model(machine)


# --- Manual endpoints

@router.get("/machines/{machine_id}/manual", response_model=ManualOut)
async def get_machine_manual(
    machine_id: str,
    machine_repo: MachineRepository = Depends(get_machine_repository),
    manual_repo: ManualRepository = Depends(get_manual_repository),
) -> ManualOut:
    """
    Singular, not a collection: a machine has at most one manual. The two 404s below are different failures and say so,
    because "this machine does not exist" and "this machine has no manual
    registered" send the caller looking in completely different places.
    """
    if await machine_repo.get_machine(machine_id) is None:
        raise HTTPException(status_code=404, detail=f"Machine '{machine_id}' not found")

    manual = await manual_repo.get_by_machine(machine_id)
    if manual is None:
        raise HTTPException(
            status_code=404, detail=f"No manual registered for machine '{machine_id}'"
        )
    return ManualOut.from_model(manual)


@router.get("/manuals/{manual_id}", response_model=ManualOut)
async def get_manual(
    manual_id: str,
    manual_repo: ManualRepository = Depends(get_manual_repository),
) -> ManualOut:
    manual = await manual_repo.get_manual(manual_id)
    if manual is None:
        raise HTTPException(status_code=404, detail=f"Manual '{manual_id}' not found")
    return ManualOut.from_model(manual)


@router.get("/manuals/{manual_id}/file")
async def download_manual(
    manual_id: str,
    manual_repo: ManualRepository = Depends(get_manual_repository),
) -> FileResponse:
    """
    Serves the PDF itself. This is the only place storage_path is used, and
    it never leaves the process: the client gets bytes, not a path.

    The row and the file can disagree — the DB says the manual exists while
    the file has been moved, or the volume was not mounted — so the check
    below is the difference between a clear 404 and a 500 with a stack trace.
    """
    manual = await manual_repo.get_manual(manual_id)
    if manual is None:
        raise HTTPException(status_code=404, detail=f"Manual '{manual_id}' not found")

    path = Path(manual.storage_path)
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"File for manual '{manual_id}' is missing on the server",
        )

    return FileResponse(
        path=path,
        media_type=manual.content_type,
        filename=manual.filename,   # what the browser saves it as
    )