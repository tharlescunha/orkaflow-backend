from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.worker_parameter import WorkerParameterRead, WorkerParameterRequest
from app.services.worker_service import WorkerService

router = APIRouter(prefix="/worker/parameters", tags=["Worker Parameters"])

MOCK_WORKER_PARAMETERS: dict[str, str] = {
    "worker-url": "https://github.com/tharlescunha/worker-url.git",
}


@router.post("/{key}", response_model=WorkerParameterRead)
def get_worker_parameter(
    key: str,
    payload: WorkerParameterRequest,
    db: Session = Depends(get_db),
):
    service = WorkerService(db)

    # 🔥 padrão correto do seu sistema
    service._authenticate_runner(payload.uuid, payload.token)

    value = MOCK_WORKER_PARAMETERS.get(key)
    if value is None:
        raise HTTPException(
            status_code=404,
            detail=f"Parâmetro '{key}' não encontrado.",
        )

    return WorkerParameterRead(
        key=key,
        value=value,
    )
