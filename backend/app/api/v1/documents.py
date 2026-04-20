"""Document download routes."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.db.models import LetterVersion

router = APIRouter()


@router.get("/{version_id}/download")
def download_document(version_id: str, db: Session = Depends(get_db)) -> FileResponse:
    version = db.get(LetterVersion, version_id)
    if version is None or not version.pdf_storage_key:
        raise HTTPException(status_code=404, detail="Document not found")
    path = Path(version.pdf_storage_key)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Document file missing")
    return FileResponse(path, media_type="application/pdf", filename=f"{version_id}.pdf")
