from __future__ import annotations
import time
import uuid
from typing import Dict, List, Optional, Tuple
from app.ai.reid import reid_engine
from app.core.config import settings
from app.models.incident import IncidentSeverity, IncidentType, SecurityIncident
from app.models.observation import PersonObservation
from app.repositories.elasticsearch import es_repo

class GlobalPersonProfile:
    def __init__(self, global_person_id: str, initial_reid_vec: List[float], employee_id: Optional[str] = None):
        self.global_person_id = global_person_id
        self.reid_embeddings: List[List[float]] = [initial_reid_vec]
        self.employee_id = employee_id
        self.last_seen_camera: Optional[str] = None
        self.last_seen_timestamp: float = time.time()
        self.movement_history: List[Dict[str, Any]] = []

    def add_observation(self, camera_id: str, reid_vec: List[float], timestamp: float, movement_dir: Optional[str] = None):
        self.reid_embeddings.append(reid_vec)
        if len(self.reid_embeddings) > 10:
            self.reid_embeddings.pop(0)
        self.last_seen_camera = camera_id
        self.last_seen_timestamp = timestamp
        self.movement_history.append({
            "camera_id": camera_id,
            "timestamp": timestamp,
            "movement_direction": movement_dir,
        })

class MultiCameraCorrelationEngine:
    """Implements Section 12 Multi-Camera Correlation assigning global_person_ids across cameras."""
    def __init__(self):
        self.similarity_threshold = settings.multi_camera.reid_similarity_threshold
        self.max_transit_sec = settings.multi_camera.max_transit_time_seconds
        self.min_transit_sec = settings.multi_camera.min_transit_time_seconds
        # In-memory tracking of active global person profiles
        self.active_profiles: Dict[str, GlobalPersonProfile] = {}

    async def correlate_observation(
        self,
        camera_id: str,
        local_track_id: int,
        reid_vector: List[float],
        employee_id: Optional[str] = None,
        movement_direction: Optional[str] = None,
        timestamp: Optional[float] = None
    ) -> str:
        ts = timestamp or time.time()
        best_match_id: Optional[str] = None
        highest_sim = 0.0

        # Compare against active profiles
        for g_id, profile in list(self.active_profiles.items()):
            time_diff = abs(ts - profile.last_seen_timestamp)
            
            # If expired beyond max transit time, remove from active pool
            if time_diff > self.max_transit_sec:
                continue

            # Compute similarity against representative profile embedding
            sim = reid_engine.cosine_similarity(reid_vector, profile.reid_embeddings[-1])
            if sim > highest_sim and sim >= self.similarity_threshold:
                highest_sim = sim
                best_match_id = g_id

        if best_match_id:
            profile = self.active_profiles[best_match_id]
            profile.add_observation(camera_id, reid_vector, ts, movement_direction)
            if employee_id and not profile.employee_id:
                profile.employee_id = employee_id
            global_id = best_match_id
        else:
            # Create new global person ID
            global_id = f"GLOBAL-{uuid.uuid4().hex[:8].upper()}"
            new_profile = GlobalPersonProfile(global_id, reid_vector, employee_id)
            new_profile.add_observation(camera_id, reid_vector, ts, movement_direction)
            self.active_profiles[global_id] = new_profile

        # Record observation in repository
        obs = PersonObservation(
            observation_id=f"OBS-{uuid.uuid4().hex[:8].upper()}",
            global_person_id=global_id,
            camera_id=camera_id,
            local_track_id=local_track_id,
            employee_id=employee_id,
            identity_status="CONFIRMED" if employee_id else "TRACKED",
            movement_direction=movement_direction,
            body_score=highest_sim if best_match_id else None,
        )
        await es_repo.index_document("person_observations", obs.observation_id, obs.model_dump(mode="json"))

        return global_id

multi_camera_engine = MultiCameraCorrelationEngine()
