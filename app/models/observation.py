from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field

class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float

class PersonObservation(BaseModel):
    observation_id: str
    global_person_id: Optional[str] = None
    camera_id: str
    local_track_id: int
    employee_id: Optional[str] = None
    identity_status: str = "UNKNOWN"  # CONFIRMED, CANDIDATE, UNKNOWN, MISMATCH
    bbox: Optional[BoundingBox] = None
    face_score: Optional[float] = None
    body_score: Optional[float] = None
    liveness_score: Optional[float] = None
    face_quality: Optional[float] = None
    movement_direction: Optional[str] = None  # ENTERING, EXITING, PASSING, STATIONARY
    zone_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
