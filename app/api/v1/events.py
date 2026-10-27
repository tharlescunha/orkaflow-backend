# app/api/v1/events.py
"""Eventos: regras "Quando → Então" por robô (requisições HTTP ao fim da task)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.schemas.event import (
    EventRuleCreate,
    EventRuleRead,
    EventRuleUpdate,
    EventRunDetail,
    EventRunRead,
    EventTestRequest,
    EventTriggerRead,
    EventVariableRead,
)
from app.services import event_service as service

router = APIRouter(prefix="/events", tags=["Events"], dependencies=[Depends(require_admin)])


@router.get("/triggers", response_model=list[EventTriggerRead])
def list_triggers():
    return [{"type": t, "label": label, "description": desc} for t, label, desc in service.TRIGGERS]


@router.get("/variables", response_model=list[EventVariableRead])
def list_variables():
    return [{"name": n, "description": d, "example": e} for n, d, e in service.VARIABLES]


@router.get("/rules", response_model=list[EventRuleRead])
def list_rules(active: bool | None = Query(default=None), db: Session = Depends(get_db)):
    return service.list_rules(db, active=active)


@router.post("/rules", response_model=EventRuleRead, status_code=201)
def create_rule(payload: EventRuleCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    rule = service.create_rule(db, payload.model_dump(), created_by=getattr(current_user, "id", None))
    return service.rule_to_read(db, rule)


@router.get("/rules/{rule_id}", response_model=EventRuleRead)
def get_rule(rule_id: int, db: Session = Depends(get_db)):
    return service.rule_to_read(db, service.get_rule(db, rule_id))


@router.put("/rules/{rule_id}", response_model=EventRuleRead)
def update_rule(rule_id: int, payload: EventRuleUpdate, db: Session = Depends(get_db)):
    rule = service.update_rule(db, rule_id, payload.model_dump())
    return service.rule_to_read(db, rule)


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    service.delete_rule(db, rule_id)
    return {"message": "Evento removido."}


@router.post("/rules/{rule_id}/test", response_model=EventRunDetail)
def test_rule(rule_id: int, payload: EventTestRequest | None = None, db: Session = Depends(get_db)):
    run = service.run_test(db, rule_id, task_id=payload.task_id if payload else None)
    return service.run_detail(run)


@router.get("/runs", response_model=list[EventRunRead])
def list_runs(
    rule_id: int | None = Query(default=None),
    task_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return [service.run_to_read(run) for run in service.list_runs(db, rule_id=rule_id, task_id=task_id, limit=limit)]


@router.get("/runs/{run_id}", response_model=EventRunDetail)
def get_run(run_id: int, db: Session = Depends(get_db)):
    return service.run_detail(service.get_run(db, run_id))
