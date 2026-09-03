from __future__ import annotations
import time
import uuid
from typing import Dict, List, Optional
from app.core.config import settings
from app.core.logging import TAILGATING_INCIDENTS_TOTAL, logger
from app.models.incident import IncidentSeverity, IncidentType, SecurityIncident
from app.repositories.elasticsearch import es_repo

class DoorAccessSession:
    def __init__(self, door_id: str, timestamp: float, authorized_employee_id: Optional[str] = None):
        self.door_id = door_id
        self.auth_timestamp = timestamp
        self.authorized_employee_id = authorized_employee_id
        self.expected_entrants = 1
        self.detected_crossing_track_ids: List[int] = []
        self.door_opened = False
        self.door_opened_at: Optional[float] = None
        self.is_closed = False

class TailgatingDetector:
    """Implements Section 11 Tailgating Detection Algorithm across entry boundary crossings."""
    def __init__(self):
        self.auth_window_sec = settings.tailgating.authentication_window_seconds
        self.crossing_window_sec = settings.tailgating.door_crossing_window_seconds
        # Active door sessions: door_id -> DoorAccessSession
        self.active_sessions: Dict[str, DoorAccessSession] = {}

    def record_card_authentication(self, door_id: str, employee_id: Optional[str] = None) -> DoorAccessSession:
        now = time.time()
        # If an existing session is within authentication window, accumulate expected entrants (multi-badge)
        if door_id in self.active_sessions:
            session = self.active_sessions[door_id]
            if (now - session.auth_timestamp) <= self.auth_window_sec:
                session.expected_entrants += 1
                return session

        session = DoorAccessSession(door_id=door_id, timestamp=now, authorized_employee_id=employee_id)
        self.active_sessions[door_id] = session
        return session

    def record_door_open(self, door_id: str):
        now = time.time()
        if door_id in self.active_sessions:
            session = self.active_sessions[door_id]
            session.door_opened = True
            session.door_opened_at = now

    async def record_track_crossing(
        self,
        door_id: str,
        track_id: int,
        camera_id: Optional[str] = None
    ) -> Optional[SecurityIncident]:
        """Called when a tracked person crosses the physical door boundary into the secure zone."""
        now = time.time()
        session = self.active_sessions.get(door_id)

        # If no active authenticated session exists, any crossing is unauthorized
        if not session or (now - session.auth_timestamp) > (self.auth_window_sec + self.crossing_window_sec):
            # Unauthorized Entry Incident
            incident = SecurityIncident(
                incident_id=f"INC-UNAUTH-{uuid.uuid4().hex[:8].upper()}",
                incident_type=IncidentType.UNAUTHORIZED_ZONE_ENTRY,
                severity=IncidentSeverity.CRITICAL,
                door_id=door_id,
                camera_id=camera_id,
                description=f"Person track #{track_id} entered door {door_id} with no valid authentication event.",
                evidence={"track_id": track_id, "timestamp": now},
            )
            await es_repo.index_document("security_incidents", incident.incident_id, incident.model_dump(mode="json"))
            return incident

        if track_id not in session.detected_crossing_track_ids:
            session.detected_crossing_track_ids.append(track_id)

        actual_count = len(session.detected_crossing_track_ids)
        expected_count = session.expected_entrants

        # Step 8 & 9: Compare expected vs actual entrants
        if actual_count > expected_count:
            TAILGATING_INCIDENTS_TOTAL.labels(door_id=door_id, severity="HIGH").inc()
            logger.warning(
                "Tailgating detected at door boundary",
                door_id=door_id,
                actual=actual_count,
                expected=expected_count,
                track_id=track_id
            )
            
            incident = SecurityIncident(
                incident_id=f"INC-TG-{uuid.uuid4().hex[:8].upper()}",
                incident_type=IncidentType.TAILGATING,
                severity=IncidentSeverity.HIGH,
                door_id=door_id,
                camera_id=camera_id,
                employee_id=session.authorized_employee_id,
                description=f"Tailgating detected at door {door_id}: {actual_count} people entered on {expected_count} badge swipe(s).",
                evidence={
                    "expected_entrants": expected_count,
                    "actual_entrants": actual_count,
                    "crossing_track_ids": session.detected_crossing_track_ids,
                    "tailgating_track_id": track_id,
                    "authorized_employee": session.authorized_employee_id,
                },
            )
            await es_repo.index_document("security_incidents", incident.incident_id, incident.model_dump(mode="json"))
            return incident

        return None

tailgating_detector = TailgatingDetector()
