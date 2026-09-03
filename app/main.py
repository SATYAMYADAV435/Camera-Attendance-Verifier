from __future__ import annotations
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.api.auth import router as auth_router
from app.api.employees import router as employees_router
from app.api.access import router as access_router
from app.api.cameras import router as cameras_router
from app.api.events import events_router, incidents_router
from app.api.dashboard import router as dashboard_router
from app.api.policies import policies_router, audit_router
from app.core.config import settings
from app.core.logging import configure_logging, logger
from app.repositories.elasticsearch import es_repo
from app.repositories.redis import redis_repo
from app.workers.health_worker import health_worker

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    configure_logging(settings.system.environment)
    logger.info("Initializing Intelligent Office Access Management System...", version="1.0.0")
    
    await es_repo.connect()
    await redis_repo.connect()
    await health_worker.start()
    
    # Pre-populate demo seed data for initial turn-key experience
    await _seed_demo_data()
    
    yield
    
    # Shutdown tasks
    logger.info("Shutting down workers and storage connections...")
    await health_worker.stop()
    await es_repo.close()
    await redis_repo.close()

app = FastAPI(
    title=settings.system.app_name,
    description="P-002: Multi-Camera AI Office Access Management System with Biometric Fusion & Physical Analytics",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers under prefix
api_prefix = settings.system.api_prefix
app.include_router(auth_router, prefix=api_prefix)
app.include_router(employees_router, prefix=api_prefix)
app.include_router(access_router, prefix=api_prefix)
app.include_router(cameras_router, prefix=api_prefix)
app.include_router(events_router, prefix=api_prefix)
app.include_router(incidents_router, prefix=api_prefix)
app.include_router(dashboard_router, prefix=api_prefix)
app.include_router(policies_router, prefix=api_prefix)
app.include_router(audit_router, prefix=api_prefix)

# Mount Static UI Files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h1>Intelligent Office Access Management API Active</h1><p>Visit <a href='/docs'>/docs</a></p>")

# Observability endpoints (§22)
@app.get("/health/live")
async def liveness_probe():
    return {"status": "LIVE", "app": settings.system.app_name}

@app.get("/health/ready")
async def readiness_probe():
    return {
        "status": "READY",
        "elasticsearch_connected": es_repo.is_connected,
        "redis_connected": redis_repo.is_connected,
    }

@app.get("/metrics")
async def prometheus_metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

async def _seed_demo_data():
    """Seeds initial test cameras and employees if repository is empty."""
    from app.models.camera import Camera, CameraStatus
    from app.models.employee import AccessLevel, Employee, EmployeeStatus, EnrollmentStatus
    from app.core.security import biometric_crypto
    import numpy as np

    # Seed / Update cameras
    cam1 = Camera(
        camera_id="CAM-01-ENTRANCE",
        name="Main Lobby Entrance (Webcam 0)",
        location="Ground Floor Lobby North",
        door_id="DOOR-MAIN-ENTRANCE",
        zone_id="MAIN_LOBBY",
        rtsp_url="0", # Physical USB / Laptop Webcam 0
        expected_fps=30.0,
        status=CameraStatus.ONLINE,
    )
    cam2 = Camera(
        camera_id="CAM-02-CORRIDOR",
        name="Executive Suite Corridor",
        location="Floor 3 West",
        door_id="DOOR-EXEC-SUITE",
        zone_id="EXEC_ZONE",
        rtsp_url="mock", # Simulated Corridor Feed
        expected_fps=30.0,
        status=CameraStatus.ONLINE,
    )
    await es_repo.index_document("cameras", cam1.camera_id, cam1.model_dump(mode="json"))
    await es_repo.index_document("cameras", cam2.camera_id, cam2.model_dump(mode="json"))
    logger.info("Configured cameras: CAM-01-ENTRANCE linked to physical Webcam (device 0).")

    # Check if employees exist
    existing_emps = await es_repo.search_documents("employees", limit=1)
    if not existing_emps:
        # Generate representative 512-dim unit vector
        dummy_vec = np.zeros(512, dtype=np.float32)
        dummy_vec[0] = 1.0
        encrypted_vec = biometric_crypto.encrypt_vector(dummy_vec.tolist())

        emp1 = Employee(
            employee_id="EMP-1001",
            employee_code="SEC-8821",
            name="Alice Vance",
            department="Security Engineering",
            role="Lead Security Architect",
            status=EmployeeStatus.ACTIVE,
            access_level=AccessLevel.ADMIN_FACILITY,
            card_id="CARD-001",
            face_enrollment_status=EnrollmentStatus.ENROLLED,
            person_reid_status=EnrollmentStatus.ENROLLED,
            encrypted_face_embedding=encrypted_vec,
            encrypted_body_embedding=encrypted_vec,
        )
        # Store raw in memory cache for kNN match in demo
        doc1 = emp1.model_dump(mode="json")
        doc1["face_embedding_raw"] = dummy_vec.tolist()
        await es_repo.index_document("employees", emp1.employee_id, doc1)

        emp2 = Employee(
            employee_id="EMP-1002",
            employee_code="DEV-4419",
            name="Bob Martinez",
            department="Core Infrastructure",
            role="Staff Cloud Engineer",
            status=EmployeeStatus.ACTIVE,
            access_level=AccessLevel.STANDARD,
            card_id="CARD-002",
            face_enrollment_status=EnrollmentStatus.ENROLLED,
            person_reid_status=EnrollmentStatus.ENROLLED,
        )
        dummy_vec2 = np.zeros(512, dtype=np.float32)
        dummy_vec2[1] = 1.0
        doc2 = emp2.model_dump(mode="json")
        doc2["face_embedding_raw"] = dummy_vec2.tolist()
        await es_repo.index_document("employees", emp2.employee_id, doc2)
        logger.info("Seeded initial employees.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
