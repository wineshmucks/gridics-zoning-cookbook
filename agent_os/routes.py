"""FastAPI routes for direct Gridics and feasibility access."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from agent_os.tools.cookbook_tools import run_instant_feasibility
from agent_os.tools.gridics_tools import get_markets, get_property_record, search_parcels

gridics_router = APIRouter(prefix="/api/gridics", tags=["gridics"])
feasibility_router = APIRouter(prefix="/api", tags=["feasibility"])


@gridics_router.get("/markets")
def markets() -> dict:
    try:
        return get_markets()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@gridics_router.get("/property-record")
def property_record(
    state_env: str = Query(...),
    address: str = Query(...),
    zip_code: str = Query(..., alias="zipCode"),
) -> dict:
    try:
        return get_property_record(state_env=state_env, address=address, zip_code=zip_code)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@gridics_router.get("/search")
def search(search_polygon: str = Query(..., alias="searchPolygon"), page: int = Query(1, ge=1)) -> dict:
    try:
        return search_parcels(search_polygon=search_polygon, page=page)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@feasibility_router.post("/instant-feasibility")
def instant_feasibility(payload: dict) -> dict:
    try:
        return run_instant_feasibility(**payload)
    except TypeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
