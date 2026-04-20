"""Direct Gridics proxy routes exposed from the UZone backend."""

from fastapi import APIRouter, HTTPException, Query

from app.services.gridics_client import _build_gridics_client

router = APIRouter()


@router.get("/property-record")
def get_property_record(
    state_env: str = Query(...),
    address: str = Query(...),
    zip_code: str = Query(..., alias="zipCode"),
) -> dict:
    try:
        client = _build_gridics_client()
        return client.get_property_record(
            state_env=state_env,
            address=address,
            zip_code=zip_code,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
