from __future__ import annotations
import hashlib
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
import cv2
import numpy as np
from app.core.config import settings
from app.core.logging import ACTIVE_CAMERAS_GAUGE, CAMERA_FAILURES_TOTAL, logger
from app.models.camera import CameraFailureType, CameraHealthRecord, CameraStatus, MaintenanceTicket
from app.models.incident import IncidentSeverity, IncidentType, SecurityIncident
from app.repositories.elasticsearch import es_repo

class CameraHealthMonitor:
    """Monitors connectivity, heartbeat, FPS, latency, frozen/black frames, and raises alerts."""
    def __init__(self):
        self.heartbeat_timeout = settings.camera.heartbeat_timeout_seconds
        self.failure_timeout = settings.camera.failure_timeout_seconds
        self.blur_threshold = settings.camera.blur_laplacian_threshold
        
        # Tracking states per camera: camera_id -> dict
        self.camera_states: Dict[str, Dict[str, Any]] = {}

    def register_frame(self, camera_id: str, frame: np.ndarray, timestamp: Optional[float] = None) -> CameraHealthRecord:
        now = timestamp or time.time()
        if camera_id not in self.camera_states:
            self.camera_states[camera_id] = {
                "last_frame_time": now,
                "last_heartbeat": now,
                "frame_count": 0,
                "fps_start_time": now,
                "fps": 30.0,
                "last_frame_hash": None,
                "frozen_count": 0,
                "status": CameraStatus.ONLINE,
                "latency_ms": 20.0,
            }

        state = self.camera_states[camera_id]
        state["frame_count"] += 1
        state["last_frame_time"] = now
        
        # Calculate instantaneous FPS over 30-frame window
        elapsed = now - state["fps_start_time"]
        if state["frame_count"] >= 30 and elapsed > 0:
            state["fps"] = float(state["frame_count"] / elapsed)
            state["frame_count"] = 0
            state["fps_start_time"] = now

        # 1. Blur evaluation
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # 2. Frozen frame evaluation (hash identical check)
        frame_hash = hashlib.md5(gray.tobytes()).hexdigest()
        if state["last_frame_hash"] == frame_hash:
            state["frozen_count"] += 1
        else:
            state["frozen_count"] = 0
        state["last_frame_hash"] = frame_hash

        # Determine failure condition
        failure_type: Optional[CameraFailureType] = None
        status = CameraStatus.ONLINE

        if state["frozen_count"] >= settings.camera.frozen_frame_threshold:
            status = CameraStatus.DEGRADED
            failure_type = CameraFailureType.FROZEN_FRAME
        elif np.mean(gray) < 5.0:
            status = CameraStatus.DEGRADED
            failure_type = CameraFailureType.BLACK_FRAME
        elif blur_score < self.blur_threshold:
            status = CameraStatus.DEGRADED
            failure_type = CameraFailureType.EXCESSIVE_BLUR

        state["status"] = status

        record = CameraHealthRecord(
            camera_id=camera_id,
            status=status,
            fps=round(state["fps"], 2),
            latency_ms=state["latency_ms"],
            stream_age_seconds=round(now - state["last_frame_time"], 2),
            blur_score=round(blur_score, 2),
            frozen_frame_count=state["frozen_count"],
            failure_type=failure_type,
            last_heartbeat=datetime.fromtimestamp(state["last_heartbeat"], tz=timezone.utc),
            timestamp=datetime.fromtimestamp(now, tz=timezone.utc),
        )
        return record

    async def check_heartbeat_and_timeout(self, camera_id: str) -> Tuple[CameraStatus, Optional[CameraFailureType]]:
        now = time.time()
        state = self.camera_states.get(camera_id)
        if not state:
            return CameraStatus.OFFLINE, CameraFailureType.NO_FRAMES

        stream_age = now - state["last_frame_time"]
        heartbeat_age = now - state["last_heartbeat"]

        if stream_age > self.failure_timeout or heartbeat_age > self.failure_timeout:
            state["status"] = CameraStatus.OFFLINE
            failure_type = CameraFailureType.HEARTBEAT_TIMEOUT
            CAMERA_FAILURES_TOTAL.labels(camera_id=camera_id, failure_type="TIMEOUT").inc()
            
            # Create incident & maintenance ticket
            ticket = MaintenanceTicket(
                ticket_id=f"TICK-{uuid.uuid4().hex[:8].upper()}",
                camera_id=camera_id,
                failure_type=failure_type,
                description=f"Camera {camera_id} stopped sending frames/heartbeat for {stream_age:.1f}s.",
            )
            await es_repo.index_document("maintenance_tickets", ticket.ticket_id, ticket.model_dump(mode="json"))

            incident = SecurityIncident(
                incident_id=f"INC-CAM-{uuid.uuid4().hex[:8].upper()}",
                incident_type=IncidentType.CAMERA_FAILURE,
                severity=IncidentSeverity.CRITICAL,
                camera_id=camera_id,
                description=f"Critical camera failure: {camera_id} is OFFLINE.",
                evidence={"stream_age_seconds": stream_age, "failure_type": failure_type.value},
            )
            await es_repo.index_document("security_incidents", incident.incident_id, incident.model_dump(mode="json"))
            return CameraStatus.OFFLINE, failure_type

        return state["status"], None

    def record_heartbeat(self, camera_id: str):
        now = time.time()
        if camera_id in self.camera_states:
            self.camera_states[camera_id]["last_heartbeat"] = now
            if self.camera_states[camera_id]["status"] == CameraStatus.OFFLINE:
                self.camera_states[camera_id]["status"] = CameraStatus.ONLINE

camera_health_monitor = CameraHealthMonitor()
