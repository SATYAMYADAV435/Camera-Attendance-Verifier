from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class EmployeeStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"
    PENDING_ENROLLMENT = "PENDING_ENROLLMENT"

class AccessLevel(str, Enum):
    STANDARD = "STANDARD"
    RESTRICTED = "RESTRICTED"
    EXECUTIVE = "EXECUTIVE"
    ADMIN_FACILITY = "ADMIN_FACILITY"
    VISITOR = "VISITOR"

class EnrollmentStatus(str, Enum):
    NOT_ENROLLED = "NOT_ENROLLED"
    PARTIAL = "PARTIAL"
    ENROLLED = "ENROLLED"
    REVOKED = "REVOKED"

class EmployeeBase(BaseModel):
    employee_code: str = Field(..., description="Unique employee badge/alphanumeric code")
    name: str
    department: str
    role: str
    status: EmployeeStatus = EmployeeStatus.ACTIVE
    access_level: AccessLevel = AccessLevel.STANDARD
    card_id: Optional[str] = None

class EmployeeCreate(EmployeeBase):
    pass

class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None
    status: Optional[EmployeeStatus] = None
    access_level: Optional[AccessLevel] = None
    card_id: Optional[str] = None

class Employee(EmployeeBase):
    employee_id: str
    face_enrollment_status: EnrollmentStatus = EnrollmentStatus.NOT_ENROLLED
    person_reid_status: EnrollmentStatus = EnrollmentStatus.NOT_ENROLLED
    enrollment_version: int = 1
    # Note: Raw encrypted vectors are stored internally, never exposed in public response
    encrypted_face_embedding: Optional[str] = Field(None, exclude=True)
    encrypted_body_embedding: Optional[str] = Field(None, exclude=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class EmployeePublic(EmployeeBase):
    employee_id: str
    face_enrollment_status: EnrollmentStatus
    person_reid_status: EnrollmentStatus
    enrollment_version: int
    created_at: datetime
    updated_at: datetime

class FaceEnrollmentRequest(BaseModel):
    # Base64 image frames or embedding vectors
    image_base64: Optional[str] = None
    raw_embedding: Optional[List[float]] = None
    notes: Optional[str] = None

class PersonReidEnrollmentRequest(BaseModel):
    image_base64: Optional[str] = None
    raw_embedding: Optional[List[float]] = None
    notes: Optional[str] = None
