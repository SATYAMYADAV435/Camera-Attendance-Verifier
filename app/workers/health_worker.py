from __future__ import annotations
import asyncio
from app.cameras.health import camera_health_monitor
from app.core.logging import ACTIVE_CAMERAS_GAUGE, logger
from app.repositories.elasticsearch import es_repo

class CameraHealthWorker:
    def __init__(self, check_interval_seconds: float = 10.0):
        self.check_interval_seconds = check_interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Camera health watchdog worker started.")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Camera health watchdog worker stopped.")

    async def _loop(self):
        while self._running:
            try:
                # Check health for all registered cameras
                cameras = await es_repo.search_documents("cameras", limit=500)
                online_count = 0
                for cam in cameras:
                    cam_id = cam.get("camera_id")
                    if cam_id:
                        status, failure = await camera_health_monitor.check_heartbeat_and_timeout(cam_id)
                        if status.value == "ONLINE":
                            online_count += 1
                
                ACTIVE_CAMERAS_GAUGE.set(online_count)
            except Exception as exc:
                logger.error("Error in camera health watchdog loop", error=str(exc))
            
            await asyncio.sleep(self.check_interval_seconds)

health_worker = CameraHealthWorker()
