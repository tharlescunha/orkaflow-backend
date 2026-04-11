from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/public/downloads", tags=["Public Downloads"])

BASE_DIR = Path(__file__).resolve().parents[2]
DOWNLOADS_DIR = BASE_DIR / "static" / "downloads"

ALLOWED_FILES = {
    "nssm.exe": DOWNLOADS_DIR / "nssm.exe",
    "orkaflow-worker.exe": DOWNLOADS_DIR / "orkaflow-worker.exe",
}


@router.get("/{filename}")
def download_public_file(filename: str):
    file_path = ALLOWED_FILES.get(filename)

    if not file_path:
        raise HTTPException(status_code=404, detail="Arquivo não permitido.")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/octet-stream",
    )
