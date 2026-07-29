# resources/router.py
from fastapi import APIRouter, Depends, HTTPException

from app.resources.repository import (MachineRepository, InMemoryMachineRepository, ManualRepository, InMemoryManualRepository)
from app.resources.schemas import Machine, Manual

router = APIRouter(prefix="/v1", tags=["resources"])


# The single swap point: when the real DB arrives, return the DB-backed
# implementation here and nothing else in the codebase changes.
def get_machine_repository() -> MachineRepository:
    return InMemoryMachineRepository()

def get_manual_repository() -> ManualRepository:
    return InMemoryManualRepository()

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


@router.get("/machine/{machine_id}/manuals", response_model=list[Manual])
async def list_machine_manuals(
    machine_id: str,
    machine_repo: MachineRepository=Depends(get_machine_repository),
    manual_repo: ManualRepository= Depends(get_manual_repository),
)-> list[Manual]:
    if await machine_repo.get_machine(machine_id) is None:
        raise HTTPException(status_code=404, detail=f"Machine '{machine_id}' not found")
    return await manual_repo.list_by_machine(machine_id)



@router.get("/manuals/{manual_id}", response_model=Manual)
async def get_manual(
    manual_id:str, 
    manual_repo: ManualRepository= Depends(get_manual_repository),
)-> Manual:
    manual=await manual_repo.get_manual(manual_id)
    if manual is None:
        raise HTTPException(status_code=404, detail=f"Manual '{manual_id}' not found")
    return manual