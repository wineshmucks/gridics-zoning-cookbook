"""Platform-level settings helpers."""

from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.db.models import PlatformSetting

PLATFORM_ASSISTANT_SETTINGS_KEY = "assistant_settings"


def has_platform_settings_storage(db: Session) -> bool:
    bind = db.get_bind()
    return bool(bind is not None and inspect(bind).has_table("shared_platform_settings"))


def get_platform_setting_record(db: Session, key: str) -> PlatformSetting | None:
    return db.scalar(select(PlatformSetting).where(PlatformSetting.key == key))


def get_platform_assistant_settings_json(db: Session) -> dict | None:
    if not has_platform_settings_storage(db):
        return None

    try:
        record = get_platform_setting_record(db, PLATFORM_ASSISTANT_SETTINGS_KEY)
    except ProgrammingError as exc:
        if "shared_platform_settings" in str(exc):
            db.rollback()
            return None
        raise
    if record is None or not isinstance(record.json_value, dict):
        return None
    return record.json_value


def set_platform_assistant_settings_json(db: Session, settings_json: dict) -> PlatformSetting:
    if not has_platform_settings_storage(db):
        raise RuntimeError("Platform settings storage is not available until migrations are applied.")

    record = get_platform_setting_record(db, PLATFORM_ASSISTANT_SETTINGS_KEY)
    if record is None:
        record = PlatformSetting(key=PLATFORM_ASSISTANT_SETTINGS_KEY, json_value=settings_json)
        db.add(record)
    else:
        record.json_value = settings_json
    db.commit()
    db.refresh(record)
    return record
