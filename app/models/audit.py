from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class AuditLogEntry(BaseModel):
    audit_id: str
    actor_id: str
    actor_username: str
    actor_role: str
    action: str
    target_type: str  # EMPLOYEE, CAMERA, POLICY, ENROLLMENT, INCIDENT, SYSTEM
    target_id: Optional[str] = None
    ip_hash_or_reference: Optional[str] = None
    status: str = "SUCCESS"  # SUCCESS, FAILURE, DENIED
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
