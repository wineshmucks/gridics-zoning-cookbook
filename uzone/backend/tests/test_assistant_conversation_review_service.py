"""Tests for assistant conversation review aggregation helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import AssistantMessageFeedback, AssistantRunTelemetry, AssistantTurnEvent, TenantClient
from app.services.assistant_conversation_review_service import list_assistant_conversation_reviews


def test_list_assistant_conversation_reviews_aggregates_turns_runs_and_feedback(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = session_factory()
    try:
        tenant = TenantClient(
            id="tenant-1",
            client_id="springfield",
            city_name="Springfield",
            department_name="Planning",
        )
        db.add(tenant)
        db.commit()

        created_at = datetime.now(UTC).replace(tzinfo=None)
        db.add_all(
            [
                AssistantTurnEvent(
                    tenant_client_id=tenant.id,
                    conversation_id="conversation-123",
                    message_id="message-1",
                    run_id="run-1",
                    agent_id="customer-zoning-agent",
                    intent_type="zoning-question",
                    jurisdiction_status="in_jurisdiction",
                    policy_decision="allow",
                    reason_code="resolved",
                    payload_json={"assistant_turn": {"intent_type": "zoning-question"}},
                    created_at=created_at - timedelta(minutes=2),
                ),
                AssistantTurnEvent(
                    tenant_client_id=tenant.id,
                    conversation_id="conversation-123",
                    message_id="message-2",
                    run_id="run-2",
                    agent_id="customer-zoning-agent",
                    intent_type="clarification",
                    jurisdiction_status="needs_confirmation",
                    policy_decision="clarify",
                    reason_code="address_confirmation",
                    payload_json={"assistant_turn": {"intent_type": "clarification"}},
                    created_at=created_at - timedelta(minutes=1),
                ),
                AssistantRunTelemetry(
                    tenant_client_id=tenant.id,
                    run_scope="team",
                    agent_id="customer-zoning-agent",
                    conversation_id="conversation-123",
                    run_id="run-2",
                    session_id="session-1",
                    model_provider="gemini",
                    model_name="gemini-2.5-pro",
                    model_id="gemini-2.5-pro",
                    input_tokens=12,
                    output_tokens=34,
                    total_tokens=46,
                    cost=0.09,
                    created_at=created_at - timedelta(minutes=1),
                ),
                AssistantMessageFeedback(
                    tenant_client_id=tenant.id,
                    clerk_user_id="user-1",
                    agent_id="customer-zoning-agent",
                    surface="public-assistant",
                    conversation_id="conversation-123",
                    message_id="message-2",
                    run_id="run-2",
                    feedback_value="down",
                    message_excerpt="The follow-up did not answer the question.",
                    metadata_json={"feedback_tags": ["not-answering"]},
                    created_at=created_at,
                ),
            ]
        )
        db.commit()

        monkeypatch.setattr("app.services.assistant_conversation_review_service.SessionLocal", session_factory)

        review = list_assistant_conversation_reviews(client_id="springfield", page=1, limit=20)

        assert review["summary"]["total_conversations"] == 1
        assert review["summary"]["total_turns"] == 2
        assert review["summary"]["total_runs"] == 1
        assert review["summary"]["total_feedback"] == 1
        assert review["summary"]["input_tokens"] == 12
        assert review["summary"]["output_tokens"] == 34
        assert review["conversations"][0]["conversation_id"] == "conversation-123"
        assert review["conversations"][0]["turn_count"] == 2
        assert review["conversations"][0]["runs"][0]["model_id"] == "gemini-2.5-pro"
        assert review["conversations"][0]["feedback"][0]["feedback_value"] == "down"
        assert review["conversations"][0]["turns"][1]["reason_code"] == "address_confirmation"
    finally:
        db.close()


def test_list_assistant_conversation_reviews_compacts_large_gridics_payloads(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = session_factory()
    try:
        tenant = TenantClient(
            id="tenant-1",
            client_id="springfield",
            city_name="Springfield",
            department_name="Planning",
        )
        db.add(tenant)
        db.commit()

        large_body = "x" * 5000
        db.add(
            AssistantTurnEvent(
                tenant_client_id=tenant.id,
                conversation_id="conversation-999",
                message_id="message-1",
                run_id="run-1",
                agent_id="customer-zoning-agent",
                intent_type="specific_address",
                jurisdiction_status="in_jurisdiction",
                policy_decision="allow",
                reason_code="in_scope",
                payload_json={
                    "gridics_call_log": [
                        {
                            "request": {
                                "method": "GET",
                                "url": "https://api.gridics.com/v1/property-record",
                                "path": "/property-record",
                                "params": {"address": "3148 Mary St, Miami, FL 33133"},
                            },
                            "response": {
                                "status_code": 200,
                                "body": large_body,
                                "json": {
                                    "status": "OK",
                                    "searchType": 4,
                                    "dataRows": 1,
                                    "data": [
                                        {
                                            "Address": "3675 S MIAMI AVE",
                                            "City": "Miami",
                                            "State": "FL",
                                            "ZipCode": "33133",
                                            "FolioNumber": "0141140050061",
                                            "CalculationStatus": 1,
                                            "LotType": 3,
                                            "Buildings": [
                                                {
                                                    "ZoningAllowance": {
                                                        "ZoneId": "CI",
                                                        "ZoneTypeId": 0,
                                                        "ZoneCombinationName": "CI",
                                                    },
                                                    "Overlays": [],
                                                    "Uses": [],
                                                    "Envelope": {
                                                        "LotAreaFeet": 79687,
                                                        "LotAreaAcres": 1.822,
                                                        "DensityUnits": 0,
                                                        "FloorAreaRatio": 0,
                                                        "MaxBuildingAreaAllowed": 317438,
                                                        "PrincipalMaxHeight": 5,
                                                        "TotalBuildingHeightFeet": None,
                                                    },
                                                    "CalibrationGeneral": {},
                                                    "Frontages": [],
                                                    "UsesStatistic": {
                                                        "totalUsesCount": 0,
                                                        "allowed": 0,
                                                        "notAllowed": 0,
                                                        "usesTypes": {},
                                                    },
                                                }
                                            ],
                                        }
                                    ],
                                },
                            },
                        }
                    ],
                    "notes": ["very large payload"],
                },
                created_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        db.commit()

        monkeypatch.setattr("app.services.assistant_conversation_review_service.SessionLocal", session_factory)

        review = list_assistant_conversation_reviews(client_id="springfield", page=1, limit=20)
        payload = review["conversations"][0]["turns"][0]["payload_json"]

        assert payload["gridics_call_log"][0]["response"]["body"]["_truncated"] is True
        assert payload["gridics_call_log"][0]["response"]["body"]["chars"] == 5000
        assert payload["gridics_call_log"][0]["response"]["json"]["data"][0]["ZoneTypeId"] == "0"
        assert payload["gridics_call_log"][0]["response"]["json"]["data"][0]["ZoneCombinationName"] == "CI"
    finally:
        db.close()
