from __future__ import annotations
import asyncio
import time
from typing import Dict, Optional
import numpy as np
from app.access_control.multi_camera import multi_camera_engine
from app.ai.detector import person_detector
from app.ai.face import face_engine
from app.ai.liveness import liveness_detector
from app.ai.reid import reid_engine
from app.ai.tracker import MultiObjectTracker
from app.cameras.health import camera_health_monitor
from app.cameras.stream import CameraStreamManager
from app.core.logging import logger

class CameraInferenceWorker:
    """Orchestrates the frame sampling, detection, tracking, biometric extraction, and correlation loop for a camera."""
    def __init__(self, camera_id: str, rtsp_url: str, sample_interval: float = 0.1):
        self.camera_id = camera_id
        self.stream = CameraStreamManager(camera_id, rtsp_url)
        self.tracker = MultiObjectTracker()
        self.sample_interval = sample_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        self.stream.connect()
        self._running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info("Camera inference worker started", camera_id=self.camera_id)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.stream.release()
        logger.info("Camera inference worker stopped", camera_id=self.camera_id)

    async def _process_loop(self):
        while self._running:
            start_t = time.time()
            ret, frame = self.stream.read_frame()
            if not ret or frame is None:
                await asyncio.sleep(0.1)
                continue

            # 1. Update camera health metrics
            camera_health_monitor.register_frame(self.camera_id, frame)

            # 2. Detect Persons
            detections = person_detector.detect_persons(frame)

            # 3. Update Multi-Object Tracking
            tracks = self.tracker.update(detections)

            # 4. Process each track
            for track in tracks:
                x1, y1, x2, y2 = int(track.bbox.x1), int(track.bbox.y1), int(track.bbox.x2), int(track.bbox.y2)
                h, w = frame.shape[:2]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)

                if (x2 - x1) > 20 and (y2 - y1) > 40:
                    person_crop = frame[y1:y2, x1:x2]
                    # Body Re-ID extraction
                    reid_vec = reid_engine.extract_embedding(person_crop)
                    direction = self.tracker.get_movement_direction(track.track_id)

                    if reid_vec:
                        await multi_camera_engine.correlate_observation(
                            camera_id=self.camera_id,
                            local_track_id=track.track_id,
                            reid_vector=reid_vec,
                            movement_direction=direction,
                        )

            # Pacing
            elapsed = time.time() - start_t
            sleep_t = max(0.01, self.sample_interval - elapsed)
            await asyncio.sleep(sleep_t)
