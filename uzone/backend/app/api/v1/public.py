"""Public tenant configuration routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.services.tenant_service import resolve_tenant_public_config, tenant_public_config_to_dict

router = APIRouter()


@router.get("/client-config")
def get_client_config(
    request: Request,
    clientid: str | None = Query(default=None),
    host: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    resolved = resolve_tenant_public_config(
        db,
        client_id=clientid,
        host=host or request.headers.get("host"),
    )
    if resolved is None:
        raise HTTPException(status_code=404, detail="Client configuration not found")
    return tenant_public_config_to_dict(resolved)
