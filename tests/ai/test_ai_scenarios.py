import pytest
import time
import numpy as np
from app.access_control.decision_engine import decision_engine
from app.access_control.multi_camera import multi_camera_engine
from app.access_control.tailgating import tailgating_detector
from app.cameras.health import camera_health_monitor
from app.core.security import biometric_crypto
from app.models.access_event import (
    AccessDecision,
    AccessEvaluationRequest,
    ConfidenceTier,
)
from app.models.camera import CameraFailureType, CameraStatus
from app.models.employee import AccessLevel, Employee, EmployeeStatus, EnrollmentStatus
from app.models.incident import IncidentType
from app.models.policy import DoorPolicy
from app.repositories.elasticsearch import es_repo

@pytest.mark.asyncio
async def test_case_01_correct_card_and_correct_employee_allows():
    """Case 1: Correct card + correct employee -> ALLOW."""
    vec = [0.0] * 512
    vec[0] = 1.0

    emp = Employee(
        employee_id="EMP-T1",
        employee_code="E-T1",
        name="Alice Test",
        department="Engineering",
        role="Dev",
        status=EmployeeStatus.ACTIVE,
        access_level=AccessLevel.STANDARD,
        card_id="CARD-T1",
        face_enrollment_status=EnrollmentStatus.ENROLLED,
    )
    doc = emp.model_dump(mode="json")
    doc["face_embedding_raw"] = vec
    await es_repo.index_document("employees", emp.employee_id, doc)

    req = AccessEvaluationRequest(
        door_id="DOOR-TEST-1",
        card_id="CARD-T1",
        face_embedding=vec,
        liveness_score=0.95,
    )
    res = await decision_engine.evaluate_access(req)
    assert res.decision == AccessDecision.ALLOW
    assert res.confidence_tier == ConfidenceTier.HIGH
    assert res.employee_id == "EMP-T1"

@pytest.mark.asyncio
async def test_case_02_wrong_person_with_card_mismatch_denies_and_alerts():
    """Case 2: Wrong person with employee's card -> mismatch, ALERT/DENY, incident created."""
    vec_alice = [0.0] * 512
    vec_alice[0] = 1.0
    vec_charlie = [0.0] * 512
    vec_charlie[2] = 1.0

    # Alice has card CARD-ALICE
    emp_alice = Employee(
        employee_id="EMP-ALICE",
        employee_code="E-A",
        name="Alice",
        department="Engineering",
        role="Dev",
        status=EmployeeStatus.ACTIVE,
        card_id="CARD-ALICE",
    )
    doc_a = emp_alice.model_dump(mode="json")
    doc_a["face_embedding_raw"] = vec_alice
    await es_repo.index_document("employees", emp_alice.employee_id, doc_a)

    # Charlie face matches vec_charlie
    emp_charlie = Employee(
        employee_id="EMP-CHARLIE",
        employee_code="E-C",
        name="Charlie",
        department="Sales",
        role="Rep",
        status=EmployeeStatus.ACTIVE,
        card_id="CARD-CHARLIE",
    )
    doc_c = emp_charlie.model_dump(mode="json")
    doc_c["face_embedding_raw"] = vec_charlie
    await es_repo.index_document("employees", emp_charlie.employee_id, doc_c)

    # Charlie presents Alice's card
    req = AccessEvaluationRequest(
        door_id="DOOR-TEST-2",
        card_id="CARD-ALICE",
        face_embedding=vec_charlie,
        liveness_score=0.95,
    )
    res = await decision_engine.evaluate_access(req)
    assert res.decision == AccessDecision.ALERT
    assert "CARD_PERSON_MISMATCH" in res.reason

@pytest.mark.asyncio
async def test_case_03_forgotten_card_biometric_only_allows():
    """Case 3: Forgotten card via approved biometric flow -> ALLOW."""
    vec = [0.0] * 512
    vec[3] = 1.0

    emp = Employee(
        employee_id="EMP-BIO",
        employee_code="E-BIO",
        name="Bio User",
        department="Engineering",
        role="Dev",
        status=EmployeeStatus.ACTIVE,
        access_level=AccessLevel.STANDARD,
    )
    doc = emp.model_dump(mode="json")
    doc["face_embedding_raw"] = vec
    await es_repo.index_document("employees", emp.employee_id, doc)

    req = AccessEvaluationRequest(
        door_id="DOOR-TEST-3",
        card_id=None,  # No card
        face_embedding=vec,
        liveness_score=0.96,
    )
    res = await decision_engine.evaluate_access(req)
    assert res.decision == AccessDecision.ALLOW
    assert res.employee_id == "EMP-BIO"

@pytest.mark.asyncio
async def test_case_04_unknown_person_denies():
    """Case 4: Unknown/unenrolled person -> DENY."""
    vec_unknown = [0.99] * 512 # Random unindexed vector
    req = AccessEvaluationRequest(
        door_id="DOOR-TEST-4",
        card_id=None,
        face_embedding=vec_unknown,
        liveness_score=0.90,
    )
    res = await decision_engine.evaluate_access(req)
    assert res.decision == AccessDecision.DENY

@pytest.mark.asyncio
async def test_case_05_liveness_failure_denies():
    """Case 5: Liveness failure/uncertainty on biometric-only -> DENY."""
    vec = [0.0] * 512
    vec[0] = 1.0
    req = AccessEvaluationRequest(
        door_id="DOOR-TEST-5",
        card_id=None,
        face_embedding=vec,
        liveness_score=0.20,  # Below 0.70 threshold (photo/screen attack)
    )
    res = await decision_engine.evaluate_access(req)
    assert res.decision == AccessDecision.DENY
    assert "LIVENESS_FAILED" in res.reason

@pytest.mark.asyncio
async def test_case_06_tailgating_detection():
    """Case 6: One card auth + two people crossing -> tailgating incident created."""
    door_id = "DOOR-TG-1"
    tailgating_detector.record_card_authentication(door_id, employee_id="EMP-ALICE")
    
    # Entrant 1 crosses (legitimate)
    inc1 = await tailgating_detector.record_track_crossing(door_id=door_id, track_id=501)
    assert inc1 is None

    # Entrant 2 crosses (tailgater!)
    inc2 = await tailgating_detector.record_track_crossing(door_id=door_id, track_id=502)
    assert inc2 is not None
    assert inc2.incident_type == IncidentType.TAILGATING

@pytest.mark.asyncio
async def test_case_07_two_legitimate_entrants_no_alert():
    """Case 7: Two legitimate badge swipes in window -> no tailgating alert."""
    door_id = "DOOR-MULTI-BADGE"
    # Badge 1
    tailgating_detector.record_card_authentication(door_id, employee_id="EMP-1")
    # Badge 2 in same window
    tailgating_detector.record_card_authentication(door_id, employee_id="EMP-2")

    inc1 = await tailgating_detector.record_track_crossing(door_id, track_id=601)
    inc2 = await tailgating_detector.record_track_crossing(door_id, track_id=602)
    assert inc1 is None
    assert inc2 is None

@pytest.mark.asyncio
async def test_case_08_multi_camera_correlation():
    """Case 8: Same person across two cameras -> correlated to one global_person_id."""
    reid_vec = [0.5] * 512

    # Camera 1 observation
    global_id_1 = await multi_camera_engine.correlate_observation(
        camera_id="CAM-1", local_track_id=1, reid_vector=reid_vec
    )
    assert global_id_1.startswith("GLOBAL-")

    # Camera 2 observation shortly after with same Re-ID vector
    global_id_2 = await multi_camera_engine.correlate_observation(
        camera_id="CAM-2", local_track_id=2, reid_vector=reid_vec
    )
    assert global_id_1 == global_id_2

@pytest.mark.asyncio
async def test_case_09_two_similar_looking_employees_not_resolved_by_nearest_match_alone():
    """Case 9: Ambiguous face distance alone must fail secure if below strict threshold."""
    # Vector with only ~0.40 cosine similarity to Alice (well below 0.65 threshold)
    ambiguous_vec = [0.4, 0.4, 0.4, 0.4, 0.4, 0.4] + [0.0] * 506
    req = AccessEvaluationRequest(
        door_id="DOOR-MAIN",
        card_id=None,
        face_embedding=ambiguous_vec,
        liveness_score=0.90,
    )
    res = await decision_engine.evaluate_access(req)
    assert res.decision == AccessDecision.DENY

@pytest.mark.asyncio
async def test_case_10_camera_timeout_offline():
    """Case 10: Camera heartbeat/frame timeout -> OFFLINE."""
    cam_id = "CAM-TIMEOUT-TEST"
    dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    camera_health_monitor.register_frame(cam_id, dummy_frame, timestamp=time.time() - 100.0)

    status, failure = await camera_health_monitor.check_heartbeat_and_timeout(cam_id)
    assert status == CameraStatus.OFFLINE
    assert failure == CameraFailureType.HEARTBEAT_TIMEOUT

@pytest.mark.asyncio
async def test_case_11_frozen_identical_frames():
    """Case 11: Frozen identical frames -> DEGRADED."""
    cam_id = "CAM-FROZEN-TEST"
    static_frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
    
    # Send identical frames to trigger frozen counter
    for _ in range(25):
        record = camera_health_monitor.register_frame(cam_id, static_frame)
    
    assert record.status == CameraStatus.DEGRADED
    assert record.failure_type == CameraFailureType.FROZEN_FRAME

@pytest.mark.asyncio
async def test_case_12_unauthorized_zone_crossing():
    """Case 12: Unauthorized zone crossing without any card swipe -> incident created."""
    door_id = "DOOR-UNAUTH-ZONE"
    incident = await tailgating_detector.record_track_crossing(door_id=door_id, track_id=999)
    assert incident is not None
    assert incident.incident_type == IncidentType.UNAUTHORIZED_ZONE_ENTRY

@pytest.mark.asyncio
async def test_case_13_deactivated_employee_denied():
    """Case 13: Deactivated employee's card/biometrics -> DENY."""
    vec = [0.0] * 512
    vec[4] = 1.0
    emp = Employee(
        employee_id="EMP-INACTIVE",
        employee_code="E-INACT",
        name="Inactive Person",
        department="Engineering",
        role="Dev",
        status=EmployeeStatus.INACTIVE,
        card_id="CARD-INACTIVE",
    )
    doc = emp.model_dump(mode="json")
    doc["face_embedding_raw"] = vec
    await es_repo.index_document("employees", emp.employee_id, doc)

    req = AccessEvaluationRequest(
        door_id="DOOR-MAIN",
        card_id="CARD-INACTIVE",
        face_embedding=vec,
        liveness_score=0.95,
    )
    res = await decision_engine.evaluate_access(req)
    assert res.decision == AccessDecision.DENY
    assert "INACTIVE" in res.reason

@pytest.mark.asyncio
async def test_case_14_elasticsearch_offline_resilient_buffering():
    """Case 14: Elasticsearch offline -> event safely buffered in memory, fail-secure rules held."""
    es_repo.is_connected = False # Simulate offline
    req = AccessEvaluationRequest(
        door_id="DOOR-MAIN",
        card_id="NON-EXISTENT",
        liveness_score=0.90,
    )
    res = await decision_engine.evaluate_access(req)
    assert res.decision == AccessDecision.DENY
    # Ensure event was recorded in memory store
    assert res.event_id in es_repo._in_memory_stores["access_events"]
