import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentUser
from app.db.engine import get_session
from app.resources.repository import (
    DbMachineRepository,
    DbManualRepository,
    MachineRepository,
    ManualRepository,
)
from app.resources.schemas import MachineOut, ManualOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["resources"])


# --- Dependency providers
#
# The providers are where the tenant scope is fixed: company_id comes from the
# authenticated user, never from the request. Because every endpoint below
# depends on one of them, every endpoint is authenticated without declaring it
# itself — an anonymous request fails in get_current_user with 401 before any
# endpoint code runs. Within one request, get_session and get_current_user are
# cached, so both repositories share the same DB session and user.

def get_machine_repository(
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> MachineRepository:
    return DbMachineRepository(session, user.company_id)


def get_manual_repository(
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> ManualRepository:
    return DbManualRepository(session, user.company_id)


# --- Machine endpoints
#
# Route order matters: FastAPI matches in declaration order, and
# /machines/by-serial/{serial_number} has the same shape as
# /machines/{machine_id}/manual. Keep the literal-segment route first.

@router.get("/machines", response_model=list[MachineOut])
async def list_machines(
    repo: MachineRepository = Depends(get_machine_repository),
) -> list[MachineOut]:
    """The caller's fleet: machines of their own company only."""
    machines = await repo.list_all()
    return [MachineOut.from_model(m) for m in machines]


@router.get("/machines/by-serial/{serial_number}", response_model=MachineOut)
async def get_machine_by_serial(
    serial_number: str,
    repo: MachineRepository = Depends(get_machine_repository),
) -> MachineOut:
    """
    Lookup by the identifier printed on the machine. The QR scheme allows
    either form of URL, and a citation coming back from the agents carries a
    serial too, so both paths land here.
    """
    machine = await repo.get_by_serial(serial_number)
    if machine is None:
        raise HTTPException(
            status_code=404, detail=f"No machine with serial '{serial_number}'"
        )
    return MachineOut.from_model(machine)


@router.get("/machines/{machine_id}", response_model=MachineOut)
async def get_machine(
    machine_id: str,
    repo: MachineRepository = Depends(get_machine_repository),
) -> MachineOut:
    # Another company's machine is indistinguishable from a missing one: 404.
    machine = await repo.get(machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail=f"Machine '{machine_id}' not found")
    return MachineOut.from_model(machine)


# --- Manual endpoints

@router.get("/machines/{machine_id}/manual", response_model=ManualOut)
async def get_machine_manual(
    machine_id: str,
    machine_repo: MachineRepository = Depends(get_machine_repository),
    manual_repo: ManualRepository = Depends(get_manual_repository),
) -> ManualOut:
    """
    Singular, not a collection: a machine has at most one manual.

    The two 404s below are different failures and say so, because "this
    machine does not exist" and "this machine has no manual registered" send
    the caller looking in completely different places.
    """
    if await machine_repo.get(machine_id) is None:
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
    manual = await manual_repo.get(manual_id)
    if manual is None:
        raise HTTPException(status_code=404, detail=f"Manual '{manual_id}' not found")
    return ManualOut.from_model(manual)


@router.get("/manuals/{manual_id}/file")
async def download_manual(
    manual_id: str,
    manual_repo: ManualRepository = Depends(get_manual_repository),
) -> FileResponse:
    """
    Serves the PDF itself. This is the only place storage_path is used, and it
    never leaves the process: the client gets bytes, not a path.

    storage_path comes from our own DB (written by the seed), never from the
    client, which only supplies an id: path traversal is not possible here.

    The browser attaches the session cookie to this request automatically, so
    a plain link or an <iframe> works with authentication and tenant scoping,
    no JavaScript download needed.
    """
    manual = await manual_repo.get(manual_id)
    if manual is None:
        raise HTTPException(status_code=404, detail=f"Manual '{manual_id}' not found")

    path = Path(manual.storage_path)
    if not path.is_file():
        # The row exists but the bytes don't: the DB and the disk disagree
        # (file moved, volume not mounted). The client did nothing wrong, so
        # this is a server fault — 500, logged so the inconsistency is seen.
        # The path goes to the log only, never to the client.
        logger.error(
            "Manual %s is registered but its file is missing at %s",
            manual_id, path,
        )
        raise HTTPException(
            status_code=500,
            detail=f"File for manual '{manual_id}' is unavailable",
        )

    return FileResponse(
        path=path,
        media_type=manual.content_type,
        filename=manual.filename,          # name used if the user saves it
        content_disposition_type="inline",  # display in the browser, don't force a download
    )
