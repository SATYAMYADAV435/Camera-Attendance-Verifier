from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class CameraStatus(str, Enum):
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    MAINTENANCE = "MAINTENANCE"

class CameraFailureType(str, Enum):
    NO_FRAMES = "NO_FRAMES"
    HEARTBEAT_TIMEOUT = "HEARTBEAT_TIMEOUT"
    FROZEN_FRAME = "FROZEN_FRAME"
    BLACK_FRAME = "BLACK_FRAME"
    EXCESSIVE_BLUR = "EXCESSIVE_BLUR"
    RTSP_CONNECTION_REFUSED = "RTSP_CONNECTION_REFUSED"
    HIGH_LATENCY = "HIGH_LATENCY"

class CameraCreate(BaseModel):
    camera_id: str
    name: str
    location: str
    door_id: Optional[str] = None
    zone_id: Optional[str] = None
    rtsp_url: str
    expected_fps: float = 30.0

class Camera(CameraCreate):
    status: CameraStatus = CameraStatus.ONLINE
    last_heartbeat: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_frame_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    current_fps: float = 30.0
    latency_ms: float = 25.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CameraHealthRecord(BaseModel):
    camera_id: str
    status: CameraStatus
    fps: float
    latency_ms: float
    stream_age_seconds: float
    blur_score: float
    frozen_frame_count: int = 0
    failure_type: Optional[CameraFailureType] = None
    last_heartbeat: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class MaintenanceTicket(BaseModel):
    ticket_id: str
    camera_id: str
    failure_type: CameraFailureType
    description: str
    priority: str = "HIGH"
    status: str = "OPEN"  # OPEN, IN_PROGRESS, RESOLVED, CLOSED
    created_by: str = "SYSTEM_WATCHDOG"
    assigned_to: Optional[str] = None
    resolution_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
