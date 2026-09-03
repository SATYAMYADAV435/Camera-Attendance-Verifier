from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.access_control.decision_engine import decision_engine
from app.access_control.tailgating import tailgating_detector
from app.core.permissions import AuthenticatedUser, UserRole, require_roles
from app.models.access_event import (
    AccessEvaluationRequest,
    AccessEvaluationResponse,
    CardEventRequest,
)
from app.repositories.elasticsearch import es_repo

router = APIRouter(prefix="/access", tags=["Access Control & Authorization"])

class TrackCrossingRequest(BaseModel):
    door_id: str
    track_id: int
    camera_id: Optional[str] = None

@router.post("/card-event")
async def handle_card_event(
    event: CardEventRequest,
    current_user: AuthenticatedUser = Depends(require_roles([
        UserRole.SECURITY_ADMIN, UserRole.SECURITY_OPERATOR, UserRole.SYSTEM_ADMIN
    ])),
):
    # Lookup card owner
    raw_emp = await es_repo.find_employee_by_card(event.card_id)
    emp_id = raw_emp.get("employee_id") if raw_emp else None
    
    # Register with tailgating session
    session = tailgating_detector.record_card_authentication(event.door_id, emp_id)
    
    return {
        "status": "CARD_EVENT_INGESTED",
        "door_id": event.door_id,
        "employee_id": emp_id,
        "expected_entrants": session.expected_entrants,
    }

@router.post("/evaluate", response_model=AccessEvaluationResponse)
async def evaluate_access_request(
    request: AccessEvaluationRequest,
    current_user: AuthenticatedUser = Depends(require_roles([
        UserRole.SECURITY_ADMIN, UserRole.SECURITY_OPERATOR, UserRole.SYSTEM_ADMIN
    ])),
):
    # Optional door policy lookup
    raw_policy = await es_repo.get_document("policies", request.door_id)
    policy = None
    if raw_policy:
        from app.models.policy import DoorPolicy
        policy = DoorPolicy(**raw_policy)

    response = await decision_engine.evaluate_access(request, door_policy=policy)
    return response

@router.post("/crossing-event")
async def handle_track_crossing(
    crossing: TrackCrossingRequest,
    current_user: AuthenticatedUser = Depends(require_roles([
        UserRole.SECURITY_ADMIN, UserRole.SECURITY_OPERATOR, UserRole.SYSTEM_ADMIN
    ])),
):
    incident = await tailgating_detector.record_track_crossing(
        door_id=crossing.door_id,
        track_id=crossing.track_id,
        camera_id=crossing.camera_id,
    )
    if incident:
        return {"status": "INCIDENT_TRIGGERED", "incident_id": incident.incident_id, "type": incident.incident_type.value}
    return {"status": "CROSSING_NORMAL", "door_id": crossing.door_id, "track_id": crossing.track_id}
