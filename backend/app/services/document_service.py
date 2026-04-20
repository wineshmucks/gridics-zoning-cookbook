"""Simple document generation helpers."""

from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import LetterDraft, LetterTemplate, LetterVersion, PropertySnapshot, Request


def render_letter_body(request: Request, snapshot: PropertySnapshot, template: LetterTemplate) -> str:
    body = template.template_body
    replacements = {
        "{{request_id}}": request.public_id,
        "{{requester_name}}": f"{request.requester_first_name} {request.requester_last_name}",
        "{{property_address}}": snapshot.address,
        "{{apn}}": snapshot.apn or "",
        "{{zoning_code}}": snapshot.zoning_code or "",
        "{{zoning_name}}": snapshot.zoning_name or "",
        "{{letter_type}}": request.letter_type,
    }
    for key, value in replacements.items():
        body = body.replace(key, value)
    return body


def active_template_for_request(db: Session, request: Request) -> LetterTemplate | None:
    return db.scalar(
        select(LetterTemplate)
        .where(
            LetterTemplate.jurisdiction_id == request.jurisdiction_id,
            LetterTemplate.letter_type == request.letter_type,
            LetterTemplate.status == "active",
        )
        .order_by(LetterTemplate.version.desc(), LetterTemplate.created_at.desc())
    )


def build_draft(db: Session, request: Request, actor_user_id: str) -> LetterDraft:
    snapshot = db.get(PropertySnapshot, request.property_snapshot_id)
    if snapshot is None:
        raise ValueError("Property snapshot not found")
    template = active_template_for_request(db, request)
    if template is None:
        raise ValueError("No active letter template found for request")

    draft = LetterDraft(
        request_id=request.id,
        template_id=template.id,
        status="ready_for_approval",
        generated_body=render_letter_body(request, snapshot, template),
        editable_sections_json=[],
        generated_from_snapshot_id=snapshot.id,
        created_by_user_id=actor_user_id,
        updated_by_user_id=actor_user_id,
    )
    return draft


def build_letter_version(request: Request, draft: LetterDraft, version_type: str, actor_user_id: str) -> LetterVersion:
    return LetterVersion(
        request_id=request.id,
        draft_id=draft.id,
        version_number=1,
        version_type=version_type,
        html_body=draft.generated_body,
        signed_by_user_id=actor_user_id if version_type == "signed_pdf" else None,
    )


def generate_pdf_for_version(version: LetterVersion) -> str:
    artifacts_dir = Path(settings.artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = artifacts_dir / f"{version.id}.pdf"
    text = re.sub(r"<[^>]+>", "", version.html_body)
    pdf = canvas.Canvas(str(pdf_path), pagesize=LETTER)
    width, height = LETTER
    y = height - 72
    for line in text.splitlines() or [text]:
        chunk = line.strip()
        if not chunk:
            y -= 14
            continue
        pdf.drawString(72, y, chunk[:100])
        y -= 14
        if y < 72:
            pdf.showPage()
            y = height - 72
    pdf.save()
    return str(pdf_path)
