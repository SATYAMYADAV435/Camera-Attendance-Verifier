from __future__ import annotations
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class DoorSecurityLevel(str, Enum):
    LOW = "LOW"
    STANDARD = "STANDARD"
    HIGH_SECURITY = "HIGH_SECURITY"
    CRITICAL_RESTRICTED = "CRITICAL_RESTRICTED"

class TimeSchedule(BaseModel):
    start_hour: int = 0  # 0-23
    end_hour: int = 24    # 1-24
    allowed_days_of_week: List[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6]) # 0=Mon, 6=Sun

class DoorPolicy(BaseModel):
    door_id: str
    door_name: str
    zone_id: str
    security_level: DoorSecurityLevel = DoorSecurityLevel.STANDARD
    allow_cardless_biometric: bool = True
    require_card_and_biometric: bool = False
    require_liveness: bool = True
    allowed_access_levels: List[str] = Field(default_factory=lambda: ["STANDARD", "EXECUTIVE", "ADMIN_FACILITY"])
    allowed_departments: Optional[List[str]] = None
    schedule: TimeSchedule = Field(default_factory=TimeSchedule)
    tailgating_detection_enabled: bool = True
