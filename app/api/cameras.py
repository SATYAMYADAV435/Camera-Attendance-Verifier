from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.cameras.health import camera_health_monitor
from app.core.permissions import AuthenticatedUser, UserRole, require_roles
from app.models.camera import (
    Camera,
    CameraCreate,
    CameraFailureType,
    CameraHealthRecord,
    CameraStatus,
    MaintenanceTicket,
)
from app.repositories.elasticsearch import es_repo

router = APIRouter(prefix="/cameras", tags=["Cameras & Maintenance"])

class HeartbeatRequest(BaseModel):
    fps: Optional[float] = None
    latency_ms: Optional[float] = None

class TicketCreateRequest(BaseModel):
    failure_type: CameraFailureType
    description: str
    priority: str = "HIGH"

@router.post("", response_model=Camera, status_code=status.HTTP_201_CREATED)
async def register_camera(
    camera_in: CameraCreate,
    current_user: AuthenticatedUser = Depends(require_roles([UserRole.SYSTEM_ADMIN, UserRole.SECURITY_ADMIN])),
):
    now = datetime.now(timezone.utc)
    cam = Camera(
        **camera_in.model_dump(),
        status=CameraStatus.ONLINE,
        last_heartbeat=now,
        last_frame_at=now,
        current_fps=camera_in.expected_fps,
        created_at=now,
    )
    await es_repo.index_document("cameras", cam.camera_id, cam.model_dump(mode="json"))
    return cam

@router.get("", response_model=List[Camera])
async def list_cameras(
    current_user: AuthenticatedUser = Depends(require_roles([
        UserRole.SYSTEM_ADMIN, UserRole.SECURITY_ADMIN, UserRole.SECURITY_OPERATOR, UserRole.MAINTENANCE_OPERATOR, UserRole.AUDITOR
    ])),
):
    docs = await es_repo.search_documents("cameras", limit=100, sort_field="created_at")
    return [Camera(**d) for d in docs]

@router.get("/{camera_id}/health", response_model=CameraHealthRecord)
async def get_camera_health(
    camera_id: str,
    current_user: AuthenticatedUser = Depends(require_roles([
        UserRole.SYSTEM_ADMIN, UserRole.SECURITY_ADMIN, UserRole.SECURITY_OPERATOR, UserRole.MAINTENANCE_OPERATOR
    ])),
):
    state = camera_health_monitor.camera_states.get(camera_id)
    if not state:
        # Return fallback status
        return CameraHealthRecord(
            camera_id=camera_id,
            status=CameraStatus.OFFLINE,
            fps=0.0,
            latency_ms=0.0,
            stream_age_seconds=999.0,
            blur_score=0.0,
            last_heartbeat=datetime.now(timezone.utc),
            timestamp=datetime.now(timezone.utc),
        )
    
    return CameraHealthRecord(
        camera_id=camera_id,
        status=state["status"],
        fps=round(state["fps"], 2),
        latency_ms=state["latency_ms"],
        stream_age_seconds=round(datetime.now(timezone.utc).timestamp() - state["last_frame_time"], 2),
        blur_score=55.0,
        frozen_frame_count=state["frozen_count"],
        last_heartbeat=datetime.fromtimestamp(state["last_heartbeat"], tz=timezone.utc),
        timestamp=datetime.now(timezone.utc),
    )

@router.post("/{camera_id}/heartbeat")
async def record_camera_heartbeat(
    camera_id: str,
    req: Optional[HeartbeatRequest] = None,
    current_user: AuthenticatedUser = Depends(require_roles([UserRole.SYSTEM_ADMIN, UserRole.MAINTENANCE_OPERATOR])),
):
    camera_health_monitor.record_heartbeat(camera_id)
    return {"status": "HEARTBEAT_ACKNOWLEDGED", "camera_id": camera_id}

@router.post("/{camera_id}/maintenance-ticket", response_model=MaintenanceTicket)
async def create_maintenance_ticket(
    camera_id: str,
    req: TicketCreateRequest,
    current_user: AuthenticatedUser = Depends(require_roles([
        UserRole.MAINTENANCE_OPERATOR, UserRole.SECURITY_ADMIN, UserRole.SYSTEM_ADMIN
    ])),
):
    ticket_id = f"TICK-{uuid.uuid4().hex[:8].upper()}"
    ticket = MaintenanceTicket(
        ticket_id=ticket_id,
        camera_id=camera_id,
        failure_type=req.failure_type,
        description=req.description,
        priority=req.priority,
        created_by=current_user.username,
    )
    await es_repo.index_document("maintenance_tickets", ticket_id, ticket.model_dump(mode="json"))
    return ticket

@router.get("/maintenance-tickets/list", response_model=List[MaintenanceTicket])
async def list_maintenance_tickets(
    current_user: AuthenticatedUser = Depends(require_roles([
        UserRole.MAINTENANCE_OPERATOR, UserRole.SECURITY_ADMIN, UserRole.SYSTEM_ADMIN
    ])),
):
    docs = await es_repo.search_documents("maintenance_tickets", limit=100, sort_field="created_at")
    return [MaintenanceTicket(**d) for d in docs]
