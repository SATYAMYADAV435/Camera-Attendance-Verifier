from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class AccessDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REVIEW = "REVIEW"
    ALERT = "ALERT"

class AuthMethod(str, Enum):
    CARD_ONLY = "CARD_ONLY"
    BIOMETRIC_ONLY = "BIOMETRIC_ONLY"
    CARD_AND_BIOMETRIC = "CARD_AND_BIOMETRIC"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"

class ConfidenceTier(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class CardEventRequest(BaseModel):
    card_id: str
    door_id: str
    reader_id: str
    timestamp: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_status: Optional[str] = "READ_SUCCESS"

class AccessEvaluationRequest(BaseModel):
    door_id: str
    card_id: Optional[str] = None
    camera_id: Optional[str] = None
    observation_id: Optional[str] = None
    local_track_id: Optional[int] = None
    # Live sensor features provided directly or looked up by observation
    face_embedding: Optional[List[float]] = None
    body_embedding: Optional[List[float]] = None
    liveness_score: Optional[float] = None
    face_quality_score: Optional[float] = None
    timestamp: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))

class AccessEvaluationResponse(BaseModel):
    event_id: str
    decision: AccessDecision
    confidence_tier: ConfidenceTier
    confidence_score: float
    employee_id: Optional[str] = None
    employee_name: Optional[str] = None
    auth_method: AuthMethod
    reason: str
    door_id: str
    camera_id: Optional[str] = None
    score_breakdown: Dict[str, float] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AccessEvent(BaseModel):
    event_id: str
    employee_id: Optional[str] = None
    card_id: Optional[str] = None
    door_id: str
    reader_id: Optional[str] = None
    camera_id: Optional[str] = None
    event_type: str = "DOOR_ACCESS"
    auth_method: AuthMethod
    decision: AccessDecision
    confidence_tier: ConfidenceTier
    confidence_score: float
    face_score: Optional[float] = None
    body_score: Optional[float] = None
    liveness_score: Optional[float] = None
    card_match: Optional[bool] = None
    reason: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
