import pytest
from datetime import datetime, timezone
from app.ai.fusion import fusion_engine
from app.access_control.policy_engine import policy_engine
from app.models.access_event import ConfidenceTier
from app.models.employee import AccessLevel, Employee, EmployeeStatus
from app.models.policy import DoorPolicy, DoorSecurityLevel, TimeSchedule

def test_fusion_engine_high_confidence():
    score, tier, breakdown = fusion_engine.compute_fusion_score(
        face_score=0.95,
        body_score=0.90,
        liveness_score=0.98,
        card_consistency=1.0,
        temporal_consistency=1.0,
        camera_context=1.0,
    )
    assert tier == ConfidenceTier.HIGH
    assert score >= 0.75
    assert breakdown["face_component"] > 0
    assert breakdown["card_component"] > 0

def test_fusion_engine_low_confidence_when_face_unknown():
    score, tier, breakdown = fusion_engine.compute_fusion_score(
        face_score=0.10,
        body_score=0.10,
        liveness_score=0.50,
        card_consistency=0.0,
        temporal_consistency=1.0,
        camera_context=1.0,
    )
    assert tier == ConfidenceTier.LOW
    assert score < 0.55

def test_policy_engine_active_employee_allowed():
    emp = Employee(
        employee_id="E-1",
        employee_code="E1",
        name="Test",
        department="Engineering",
        role="Dev",
        status=EmployeeStatus.ACTIVE,
        access_level=AccessLevel.STANDARD,
    )
    policy = DoorPolicy(
        door_id="D-1",
        door_name="Main Door",
        zone_id="Z-1",
        allowed_access_levels=["STANDARD", "EXECUTIVE"],
    )
    ok, reason = policy_engine.evaluate_policy(emp, policy)
    assert ok is True
    assert reason == "POLICY_PERMITTED"

def test_policy_engine_deactivated_employee_denied():
    emp = Employee(
        employee_id="E-2",
        employee_code="E2",
        name="Test Inactive",
        department="Engineering",
        role="Dev",
        status=EmployeeStatus.INACTIVE,
        access_level=AccessLevel.STANDARD,
    )
    policy = DoorPolicy(door_id="D-1", door_name="Main", zone_id="Z-1")
    ok, reason = policy_engine.evaluate_policy(emp, policy)
    assert ok is False
    assert "INACTIVE" in reason
