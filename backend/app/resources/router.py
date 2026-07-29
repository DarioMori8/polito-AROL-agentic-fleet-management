# resources/router.py
from fastapi import APIRouter, Depends, HTTPException

from app.resources.repository import (MachineRepository, InMemoryMachineRepository)
from app.resources.schemas import Machine

router = APIRouter(prefix="/v1", tags=["resources"])


# The single swap point: when the real DB arrives, return the DB-backed
# implementation here and nothing else in the codebase changes.
def get_machine_repository() -> MachineRepository:
    return InMemoryMachineRepository()



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

