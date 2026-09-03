from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.core.permissions import AuthenticatedUser, UserRole, require_roles
from app.models.incident import IncidentStatus, SecurityIncident
from app.services.event_service import event_service
from app.services.incident_service import incident_service

events_router = APIRouter(prefix="/events", tags=["Access Events"])
incidents_router = APIRouter(prefix="/incidents", tags=["Security Incidents"])

# Events endpoints
@events_router.get("")
async def get_events(
    employee_id: Optional[str] = None,
    camera_id: Optional[str] = None,
    door_id: Optional[str] = None,
    decision: Optional[str] = None,
    limit: int = 100,
    current_user: AuthenticatedUser = Depends(require_roles([
        UserRole.SECURITY_ADMIN, UserRole.SECURITY_OPERATOR, UserRole.SYSTEM_ADMIN, UserRole.AUDITOR
    ])),
):
    return await event_service.list_events(
        employee_id=employee_id, camera_id=camera_id, door_id=door_id, decision=decision, limit=limit
    )

@events_router.get("/{event_id}")
async def get_single_event(
    event_id: str,
    current_user: AuthenticatedUser = Depends(require_roles([
        UserRole.SECURITY_ADMIN, UserRole.SECURITY_OPERATOR, UserRole.SYSTEM_ADMIN, UserRole.AUDITOR
    ])),
):
    ev = await event_service.get_event(event_id)
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return ev

# Incidents endpoints
class IncidentUpdateRequest(BaseModel):
    status: Optional[IncidentStatus] = None
    assigned_to: Optional[str] = None
    resolution: Optional[str] = None

@incidents_router.get("")
async def list_incidents(
    incident_type: Optional[str] = None,
    severity: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = 100,
    current_user: AuthenticatedUser = Depends(require_roles([
        UserRole.SECURITY_ADMIN, UserRole.SECURITY_OPERATOR, UserRole.SYSTEM_ADMIN, UserRole.AUDITOR
    ])),
):
    return await incident_service.list_incidents(
        incident_type=incident_type, severity=severity, status=status_filter, limit=limit
    )

@incidents_router.get("/{incident_id}")
async def get_single_incident(
    incident_id: str,
    current_user: AuthenticatedUser = Depends(require_roles([
        UserRole.SECURITY_ADMIN, UserRole.SECURITY_OPERATOR, UserRole.SYSTEM_ADMIN, UserRole.AUDITOR
    ])),
):
    inc = await incident_service.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return inc

@incidents_router.patch("/{incident_id}")
async def update_incident(
    incident_id: str,
    req: IncidentUpdateRequest,
    current_user: AuthenticatedUser = Depends(require_roles([
        UserRole.SECURITY_ADMIN, UserRole.SECURITY_OPERATOR
    ])),
):
    inc = await incident_service.update_incident(
        incident_id=incident_id,
        status=req.status,
        assigned_to=req.assigned_to,
        resolution=req.resolution,
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        actor_username=current_user.username,
    )
    if not inc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return inc
