# app/api/v1/env_variables.py
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.database import get_db
from app.schemas.env_variable import (
    EnvVariableCreate,
    EnvVariableEffective,
    EnvVariableImport,
    EnvVariableImportResponse,
    EnvVariableRead,
    EnvVariableUpdate,
)
from app.services import env_variable_service as service

router = APIRouter(
    prefix="/env-variables",
    tags=["Env Variables"],
    dependencies=[Depends(require_admin)],
)


@router.get("/", response_model=list[EnvVariableRead])
def list_variables(
    scope_type: str | None = Query(default=None),
    scope_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return [service.to_read(db, var) for var in service.list_variables(db, scope_type, scope_id, search)]


# rota estática antes da parametrizada
@router.get("/effective", response_model=list[EnvVariableEffective])
def effective(
    automation_id: int = Query(...),
    runner_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Valores finais com a herança aplicada (segredos sem valor)."""
    return service.effective_variables(db, automation_id, runner_id)


@router.post("/", response_model=EnvVariableRead, status_code=status.HTTP_201_CREATED)
def create_variable(payload: EnvVariableCreate, db: Session = Depends(get_db)):
    return service.to_read(db, service.create_variable(db, payload.model_dump()))


@router.post("/import", response_model=EnvVariableImportResponse)
def import_variables(payload: EnvVariableImport, db: Session = Depends(get_db)):
    """Cria (ou atualiza, com overwrite) várias variáveis de uma vez, ex.: lidas de um .env."""
    return service.import_variables(
        db,
        payload.scope_type,
        payload.scope_id,
        [item.model_dump() for item in payload.variables],
        overwrite=payload.overwrite,
    )


@router.put("/{var_id}", response_model=EnvVariableRead)
def update_variable(var_id: int, payload: EnvVariableUpdate, db: Session = Depends(get_db)):
    return service.to_read(db, service.update_variable(db, var_id, payload.model_dump(exclude_unset=True)))


@router.delete("/{var_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_variable(var_id: int, db: Session = Depends(get_db)):
    service.delete_variable(db, var_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
