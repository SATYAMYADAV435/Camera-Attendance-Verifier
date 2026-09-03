from __future__ import annotations
import os
import time
from typing import Generator, Optional, Tuple
import cv2
import numpy as np
from app.core.logging import logger

class CameraStreamManager:
    """Manages RTSP/USB camera ingestion with synthetic test pattern fallback."""
    def __init__(self, camera_id: str, rtsp_url: str, expected_fps: float = 30.0):
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.expected_fps = expected_fps
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_synthetic = False
        self._frame_count = 0
        self._last_frame_time = time.time()
        self._last_frame: Optional[np.ndarray] = None

    def connect(self) -> bool:
        if self.rtsp_url.lower() in ("mock", "synthetic", "test") or not self.rtsp_url:
            self.is_synthetic = True
            logger.info("Operating stream in synthetic test mode", camera_id=self.camera_id)
            return True

        try:
            # Handle numeric USB index vs RTSP URL
            source = int(self.rtsp_url) if self.rtsp_url.isdigit() else self.rtsp_url
            self.cap = cv2.VideoCapture(source)
            if self.cap.isOpened():
                self.is_synthetic = False
                logger.info("Connected to camera stream", camera_id=self.camera_id, source=self.rtsp_url)
                return True
            else:
                self.is_synthetic = True
                logger.warning("Could not open stream; falling back to synthetic generator", camera_id=self.camera_id)
                return True
        except Exception as exc:
            self.is_synthetic = True
            logger.warning("Stream connection exception; using synthetic fallback", camera_id=self.camera_id, error=str(exc))
            return True

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        now = time.time()
        self._last_frame_time = now
        self._frame_count += 1

        if not self.is_synthetic and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                self._last_frame = frame
                return True, frame

        # Generate synthetic frame with animated simulated person
        h, w = 480, 640
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:] = (35, 35, 40)
        
        # Draw moving target block
        cx = int((w // 2) + (w // 4) * np.sin(self._frame_count * 0.05))
        cy = int((h // 2) + (h // 4) * np.cos(self._frame_count * 0.05))
        cv2.rectangle(frame, (cx - 30, cy - 60), (cx + 30, cy + 60), (60, 220, 120), -1)
        # Face representation
        cv2.circle(frame, (cx, cy - 35), 18, (200, 180, 150), -1)
        
        self._last_frame = frame
        return True, frame

    def release(self):
        if self.cap and self.cap.isOpened():
            self.cap.release()
            logger.info("Released camera stream", camera_id=self.camera_id)
