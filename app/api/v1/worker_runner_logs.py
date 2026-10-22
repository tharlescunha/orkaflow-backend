from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.runner_log import WorkerLogBatchRequest, WorkerLogBatchResponse
from app.services.runner_log_service import RunnerLogService

router = APIRouter(prefix="/worker/runner-logs", tags=["Worker Runner Logs"])


@router.post("/", response_model=WorkerLogBatchResponse)
def push_runner_log_lines(payload: WorkerLogBatchRequest, db: Session = Depends(get_db)):
    """Lote de linhas do worker.log da máquina (tela de Logs)."""
    service = RunnerLogService(db)
    return service.ingest(payload)
