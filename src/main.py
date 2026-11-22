"""Standalone synthetic camera sensor service.

This is NOT the entrypoint of the FastAPI app — that is ``app/main.py``
(``uvicorn app.main:app``). This file only generates synthetic frames
(or reads a real camera via ``CAMERA_SOURCE``) and logs telemetry; it
is not wired into the API, the workers, or Docker. Run it only if you
explicitly want a standalone sensor loop.
"""
import os
import sys
import time
import signal
import logging
import numpy as np

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("CameraSensor")

# Graceful termination handling
running = True

def signal_handler(signum, frame):
    global running
    logger.info(f"Received signal {signum}. Shutting down camera sensor service...")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def generate_synthetic_frame(width: int, height: int, frame_idx: int) -> np.ndarray:
    """Generates a synthetic camera sensor frame for testing environments without physical devices."""
    # Create base dark slate background
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = (30, 30, 35)

    # Dynamic animated circle simulating sensor target tracking
    center_x = int((width // 2) + (width // 4) * np.sin(frame_idx * 0.05))
    center_y = int((height // 2) + (height // 4) * np.cos(frame_idx * 0.05))
    radius = 30
    
    # Draw simple bounding box simulation in array
    y1, y2 = max(0, center_y - radius), min(height, center_y + radius)
    x1, x2 = max(0, center_x - radius), min(width, center_x + radius)
    frame[y1:y2, x1:x2] = (50, 200, 100)

    return frame

def run_camera_service():
    global running
    source_env = os.getenv("CAMERA_SOURCE", "0")
    width = int(os.getenv("FRAME_WIDTH", "640"))
    height = int(os.getenv("FRAME_HEIGHT", "480"))
    target_fps = float(os.getenv("FPS", "30"))
    frame_interval = 1.0 / target_fps if target_fps > 0 else 0.033

    logger.info("Starting Camera Sensor Service...")
    logger.info(f"Target Configuration: Source={source_env}, Resolution={width}x{height}, FPS={target_fps}")

    try:
        import cv2
        has_cv2 = True
    except ImportError:
        logger.warning("OpenCV (cv2) not found. Operating in synthetic mock frame mode.")
        has_cv2 = False

    cap = None
    use_synthetic = source_env.lower() == "mock" or not has_cv2

    if not use_synthetic and has_cv2:
        # Determine camera index vs video stream URL
        camera_idx_or_url = int(source_env) if source_env.isdigit() else source_env
        logger.info(f"Attempting connection to camera device: {camera_idx_or_url}")
        cap = cv2.VideoCapture(camera_idx_or_url)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        if not cap.isOpened():
            logger.warning(
                f"Could not open camera device '{camera_idx_or_url}'. "
                "Switching automatically to synthetic sensor simulation mode."
            )
            use_synthetic = True

    frame_count = 0
    start_time = time.time()

    logger.info("Camera stream loop initialized.")
    try:
        while running:
            loop_start = time.time()
            frame = None

            if not use_synthetic and cap and cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    logger.warning("Failed to read frame from camera device. Retrying...")
                    time.sleep(0.5)
                    continue
            else:
                frame = generate_synthetic_frame(width, height, frame_count)

            frame_count += 1

            # Log periodic telemetry every 100 frames (~3-4 seconds)
            if frame_count % 100 == 0:
                elapsed = time.time() - start_time
                avg_fps = frame_count / elapsed if elapsed > 0 else 0
                logger.info(
                    f"Sensor Telemetry: Processed {frame_count} frames | "
                    f"Avg FPS: {avg_fps:.2f} | Shape: {frame.shape if frame is not None else 'None'}"
                )

            # Frame rate pacing
            elapsed_loop = time.time() - loop_start
            sleep_time = frame_interval - elapsed_loop
            if sleep_time > 0:
                time.sleep(sleep_time)

    finally:
        if cap is not None and hasattr(cap, "isOpened") and cap.isOpened():
            cap.release()
            logger.info("Camera device released.")
        logger.info(f"Camera Sensor Service stopped. Total frames processed: {frame_count}")

if __name__ == "__main__":
    run_camera_service()
