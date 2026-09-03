from __future__ import annotations
import time
from typing import Dict, List, Optional, Tuple
import numpy as np
from app.models.observation import BoundingBox

class TrackedPerson:
    def __init__(self, track_id: int, bbox: BoundingBox, timestamp: float):
        self.track_id = track_id
        self.bbox = bbox
        self.history: List[Tuple[float, float, float]] = [(time.time(), (bbox.x1 + bbox.x2)/2, (bbox.y1 + bbox.y2)/2)]
        self.last_updated = timestamp
        self.confirmed = False
        self.hits = 1
        self.age = 1

    def update(self, bbox: BoundingBox, timestamp: float):
        self.bbox = bbox
        self.last_updated = timestamp
        self.hits += 1
        self.age += 1
        cx, cy = (bbox.x1 + bbox.x2) / 2.0, (bbox.y1 + bbox.y2) / 2.0
        self.history.append((timestamp, cx, cy))
        if len(self.history) > 30:
            self.history.pop(0)

class MultiObjectTracker:
    """Multi-object tracker associating detections across frames using IoU & spatial continuity."""
    def __init__(self, max_age_seconds: float = 2.0, iou_threshold: float = 0.3):
        self.max_age_seconds = max_age_seconds
        self.iou_threshold = iou_threshold
        self.next_track_id = 1
        self.tracks: Dict[int, TrackedPerson] = {}

    def _compute_iou(self, boxA: BoundingBox, boxB: BoundingBox) -> float:
        xA = max(boxA.x1, boxB.x1)
        yA = max(boxA.y1, boxB.y1)
        xB = min(boxA.x2, boxB.x2)
        yB = min(boxA.y2, boxB.y2)

        interArea = max(0.0, xB - xA) * max(0.0, yB - yA)
        boxAArea = (boxA.x2 - boxA.x1) * (boxA.y2 - boxA.y1)
        boxBArea = (boxB.x2 - boxB.x1) * (boxB.y2 - boxB.y1)

        unionArea = boxAArea + boxBArea - interArea
        return interArea / unionArea if unionArea > 0 else 0.0

    def update(self, detections: List[BoundingBox], timestamp: Optional[float] = None) -> List[TrackedPerson]:
        ts = timestamp or time.time()
        
        # Match detections to existing tracks via IoU
        matched_tracks = set()
        matched_detections = set()

        for det_idx, det in enumerate(detections):
            best_iou = 0.0
            best_track_id = None
            for track_id, track in self.tracks.items():
                if track_id in matched_tracks:
                    continue
                iou = self._compute_iou(det, track.bbox)
                if iou > best_iou and iou >= self.iou_threshold:
                    best_iou = iou
                    best_track_id = track_id
            
            if best_track_id is not None:
                self.tracks[best_track_id].update(det, ts)
                matched_tracks.add(best_track_id)
                matched_detections.add(det_idx)

        # Create new tracks for unmatched detections
        for det_idx, det in enumerate(detections):
            if det_idx not in matched_detections:
                new_track = TrackedPerson(self.next_track_id, det, ts)
                self.tracks[self.next_track_id] = new_track
                self.next_track_id += 1

        # Prune dead tracks
        dead_ids = [t_id for t_id, track in self.tracks.items() if (ts - track.last_updated) > self.max_age_seconds]
        for d_id in dead_ids:
            del self.tracks[d_id]

        return list(self.tracks.values())

    def get_movement_direction(self, track_id: int) -> str:
        track = self.tracks.get(track_id)
        if not track or len(track.history) < 2:
            return "STATIONARY"
        _, _, start_y = track.history[0]
        _, _, end_y = track.history[-1]
        delta_y = end_y - start_y
        if delta_y > 20:
            return "ENTERING"
        elif delta_y < -20:
            return "EXITING"
        return "PASSING"
