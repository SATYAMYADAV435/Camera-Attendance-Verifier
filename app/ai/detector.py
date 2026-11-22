from __future__ import annotations
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from app.core.config import settings
from app.core.logging import AI_INFERENCE_LATENCY_SECONDS, logger
from app.models.observation import BoundingBox

class PersonDetector:
    """Person detection pipeline with YOLOv8 Tiny/Nano backend."""
    def __init__(self, model_name: str = "yolov8n.pt"):
        self.model_name = model_name
        self.model = None
        self.is_loaded = False
        self._load_model()

    def _load_model(self):
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_name)
            self.is_loaded = True
            logger.info("YOLOv8 tiny person detector initialized successfully.", model=self.model_name)
        except Exception as exc:
            logger.warning("YOLOv8 tiny detector fallback mode activated.", error=str(exc))
            self.is_loaded = False

    def detect_persons(
        self,
        frame: np.ndarray,
        confidence_threshold: float = 0.45,
        zone_polygon: Optional[List[Tuple[float, float]]] = None
    ) -> List[BoundingBox]:
        """Detects person objects in frame using YOLOv8, returning standardized bounding boxes."""
        start_time = time.time()
        detections: List[BoundingBox] = []

        if frame is None or frame.size == 0:
            return []

        h, w = frame.shape[:2]

        if self.is_loaded and self.model is not None:
            try:
                # Run YOLOv8 inference filtering for class 0 (Person in COCO)
                results = self.model(frame, classes=[0], conf=confidence_threshold, verbose=False)
                for res in results:
                    for box in res.boxes:
                        coords = box.xyxy[0].cpu().numpy()
                        conf = float(box.conf[0].cpu().numpy())
                        x1, y1, x2, y2 = map(float, coords)
                        
                        bbox = BoundingBox(
                            x1=x1, y1=y1, x2=x2, y2=y2,
                            confidence=round(conf, 3)
                        )
                        
                        # Apply optional zone polygon filter
                        if zone_polygon:
                            center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
                            if not self._is_point_in_polygon(center, zone_polygon):
                                continue
                                
                        detections.append(bbox)
            except Exception as err:
                logger.warning("YOLOv8 inference error", error=str(err))

        # Fallback if no deep detector or synthetic pattern.
        # WARNING: this returns a synthetic centre-of-frame box with a
        # fixed 0.85 confidence — it is NOT a real detection. It exists
        # only so the demo pipeline can run without a YOLO model.
        if not detections and not self.is_loaded:
            logger.warning(
                "YOLOv8 model not loaded; returning a synthetic centre-frame "
                "detection. This is demo fallback, not a real person detection."
            )
            if np.mean(frame) > 0:
                cx, cy = w / 2.0, h / 2.0
                bw, bh = w * 0.3, h * 0.7
                detections.append(BoundingBox(
                    x1=max(0.0, cx - bw / 2.0),
                    y1=max(0.0, cy - bh / 2.0),
                    x2=min(float(w), cx + bw / 2.0),
                    y2=min(float(h), cy + bh / 2.0),
                    confidence=0.85
                ))

        latency = time.time() - start_time
        AI_INFERENCE_LATENCY_SECONDS.labels(component="person_detector_yolov8").observe(latency)
        return detections

    @staticmethod
    def _is_point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
        """Ray casting algorithm for zone polygon boundary checks."""
        x, y = point
        n = len(polygon)
        inside = False
        p1x, p1y = polygon[0]
        for i in range(n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

# Global singleton
person_detector = PersonDetector()
