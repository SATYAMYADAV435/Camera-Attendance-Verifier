from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class IncidentType(str, Enum):
    TAILGATING = "TAILGATING"
    CARD_PERSON_MISMATCH = "CARD_PERSON_MISMATCH"
    SPOOFING_ATTEMPT = "SPOOFING_ATTEMPT"
    UNAUTHORIZED_ZONE_ENTRY = "UNAUTHORIZED_ZONE_ENTRY"
    UNKNOWN_PERSON = "UNKNOWN_PERSON"
    CAMERA_FAILURE = "CAMERA_FAILURE"
    ANTI_PASSBACK_VIOLATION = "ANTI_PASSBACK_VIOLATION"
    MULTIPLE_ENTRANTS_UNAUTHORIZED = "MULTIPLE_ENTRANTS_UNAUTHORIZED"

class IncidentSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class IncidentStatus(str, Enum):
    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    FALSE_POSITIVE = "FALSE_POSITIVE"

class SecurityIncident(BaseModel):
    incident_id: str
    incident_type: IncidentType
    severity: IncidentSeverity = IncidentSeverity.HIGH
    status: IncidentStatus = IncidentStatus.NEW
    camera_id: Optional[str] = None
    door_id: Optional[str] = None
    employee_id: Optional[str] = None
    card_id: Optional[str] = None
    global_person_id: Optional[str] = None
    description: str
    evidence: Dict[str, Any] = Field(default_factory=dict)
    assigned_to: Optional[str] = None
    resolution: Optional[str] = None
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
