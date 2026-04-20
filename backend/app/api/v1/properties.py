"""Property routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.db.models import Jurisdiction, Property, PropertySnapshot, User
from app.schemas import PropertyCreate, PropertyRead, PropertySnapshotCreate, PropertySnapshotRead

router = APIRouter()


@router.post("", response_model=PropertyRead, status_code=status.HTTP_201_CREATED)
def create_property(payload: PropertyCreate, db: Session = Depends(get_db)) -> PropertyRead:
    jurisdiction = db.get(Jurisdiction, payload.jurisdiction_id)
    if jurisdiction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jurisdiction not found")

    property_record = Property(**payload.model_dump())
    db.add(property_record)
    db.commit()
    db.refresh(property_record)
    return PropertyRead.model_validate(property_record)


@router.get("/search", response_model=list[PropertyRead])
def search_properties(
    q: str | None = Query(default=None, min_length=1),
    jurisdiction_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[PropertyRead]:
    stmt = select(Property)
    if jurisdiction_id:
        stmt = stmt.where(Property.jurisdiction_id == jurisdiction_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Property.address_line1.ilike(like),
                Property.apn.ilike(like),
                Property.group_id.ilike(like),
            )
        )
    properties = db.scalars(stmt.order_by(Property.created_at.desc())).all()
    return [PropertyRead.model_validate(item) for item in properties]


@router.post(
    "/{property_id}/snapshots",
    response_model=PropertySnapshotRead,
    status_code=status.HTTP_201_CREATED,
)
def create_property_snapshot(
    property_id: str,
    payload: PropertySnapshotCreate,
    db: Session = Depends(get_db),
) -> PropertySnapshotRead:
    if payload.property_id != property_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path property_id must match payload property_id",
        )

    property_record = db.get(Property, property_id)
    if property_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    if payload.captured_by_user_id is not None and db.get(User, payload.captured_by_user_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="captured_by_user_id user not found",
        )

    snapshot = PropertySnapshot(**payload.model_dump())
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return PropertySnapshotRead.model_validate(snapshot)


@router.get("/{property_id}", response_model=PropertyRead)
def get_property(property_id: str, db: Session = Depends(get_db)) -> PropertyRead:
    property_record = db.get(Property, property_id)
    if property_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    return PropertyRead.model_validate(property_record)
