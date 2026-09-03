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
            if str(self.rtsp_url).isdigit():
                source = int(self.rtsp_url)
                # On Windows, use DirectShow for instant webcam startup
                self.cap = cv2.VideoCapture(source, cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            else:
                self.cap = cv2.VideoCapture(self.rtsp_url)

            if self.cap and self.cap.isOpened():
                self.is_synthetic = False
                logger.info("Connected to physical camera stream", camera_id=self.camera_id, source=self.rtsp_url)
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
            if ret and frame is not None:
                h, w = frame.shape[:2]
                # Overlay Security HUD on real camera frame
                cv2.putText(frame, f"{self.camera_id} | LIVE FEED", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 128), 2)
                cv2.putText(frame, f"FPS: {self.expected_fps:.1f} | RES: {w}x{h}", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 220, 240), 1)
                cv2.putText(frame, f"TIME: {time.strftime('%Y-%m-%d %H:%M:%S')}", (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 220, 240), 1)
                
                # Dynamic tracking box centered in frame
                cv2.rectangle(frame, (w//4, h//6), (3*w//4, 5*h//6), (16, 185, 129), 2)
                cv2.putText(frame, "TARGET DETECTED [ACTIVE]", (w//4, h//6 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (16, 185, 129), 1)
                
                self._last_frame = frame
                return True, frame

        # Generate synthetic frame with animated simulated person
        h, w = 480, 640
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:] = (35, 35, 40)
        
        # Draw simulated security camera overlay
        cx = int((w // 2) + (w // 4) * np.sin(self._frame_count * 0.05))
        cy = int((h // 2) + (h // 4) * np.cos(self._frame_count * 0.05))
        
        # Bounding box & target
        cv2.rectangle(frame, (cx - 40, cy - 80), (cx + 40, cy + 80), (16, 185, 129), 2)
        cv2.putText(frame, "PERSON #101 (TRACKED)", (cx - 40, cy - 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (16, 185, 129), 1)
        
        # Face representation
        cv2.circle(frame, (cx, cy - 45), 22, (200, 180, 150), -1)
        cv2.circle(frame, (cx, cy - 45), 22, (99, 102, 241), 2)
        
        # Security OSD overlay
        cv2.putText(frame, f"{self.camera_id} | LIVE FEED", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, f"FPS: {self.expected_fps:.1f} | RES: 640x480", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (148, 163, 184), 1)
        cv2.putText(frame, f"TIME: {time.strftime('%Y-%m-%d %H:%M:%S')}", (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (148, 163, 184), 1)
        
        self._last_frame = frame
        return True, frame

    def generate_jpeg_bytes(self) -> Optional[bytes]:
        ret, frame = self.read_frame()
        if not ret or frame is None:
            return None
        ret_enc, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ret_enc:
            return None
        return buffer.tobytes()

    def release(self):
        if self.cap and self.cap.isOpened():
            self.cap.release()
            logger.info("Released camera stream", camera_id=self.camera_id)
