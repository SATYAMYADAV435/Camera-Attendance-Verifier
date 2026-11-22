# P-002: Intelligent Office Access Management System

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

A multi-camera AI security demo platform that authenticates office access through **multi-signal biometric fusion**, card-event correlation, presentation attack liveness detection, cross-camera person Re-ID, physical movement analytics, and fail-secure authorization rules.

> **Honesty note — what this is and is not.** This is a working demo / portfolio
> project, not a production security system. The fusion engine, fail-secure
> decision logic, AES-256-GCM biometric encryption (`app/core/security.py`)
> and Elasticsearch/Redis stores with in-memory fallback are implemented.
> But: face "ArcFace" is a deterministic colour-histogram 512-dim fallback
> — no ArcFace/InsightFace model weights are bundled (`app/ai/face.py`);
> liveness is a heuristic texture/frequency check, not a trained
> anti-spoof model (`app/ai/liveness.py`); and person detection falls back
> to a synthetic centre-frame box when YOLOv8 cannot load
> (`app/ai/detector.py`). Do not deploy this as-is for real access control.

```
CARD + BIOMETRIC IDENTITY + LIVENESS + PERSON RE-ID + AUTHORIZATION + PHYSICAL MOVEMENT ANALYTICS = INTELLIGENT ACCESS DECISION
```

---

## Key Features

1. **Multi-Signal Identity Fusion Engine (§8)**:
   - Evaluates weighted inputs from Face Recognition (512-dim embedding — see honesty note above, not a real ArcFace model), Body/Person Re-ID, Anti-Spoofing Liveness (heuristic), Access Card consistency, and Spatio-temporal context.
   - Categorizes confidence into **HIGH**, **MEDIUM**, and **LOW** tiers.
2. **Fail-Secure Authorization**:
   - Ambiguous or sub-threshold evidence strictly results in `DENY` or `ALERT`.
   - Card/Person mismatches automatically block entry and raise critical security incidents.
3. **Step-by-Step Tailgating Detection (§11)**:
   - Correlates card swipes, door sensor open/close events, and tracking boundaries to flag unauthorized followers.
4. **Multi-Camera Correlation (§12)**:
   - Tracks and matches people across cameras using appearance embeddings and transit constraints to assign persistent `global_person_id`s.
5. **Camera Health Watchdog**:
   - Automated detection of stream dropouts, frozen frames, excessive blur, and heartbeat timeouts with automatic maintenance ticket creation.
6. **Encrypted Biometric Storage (FR-002)**:
   - Biometric vectors encrypted at rest with **AES-256-GCM**; never exposed via normal employee APIs.
7. **Role-Based Access Control (RBAC)**:
   - Enforces 6 strict roles: `SYSTEM_ADMIN`, `SECURITY_ADMIN`, `SECURITY_OPERATOR`, `MAINTENANCE_OPERATOR`, `EMPLOYEE`, `AUDITOR`.
8. **Interactive Command Dashboard**:
   - Sleek glassmorphism dark-mode UI with live event feeds, camera grids, incident triage, and biometric enrollment.

---

## Architecture Overview

```
Cameras (1..N) ────────► Video Ingestion ──► Person Detection (YOLO) ──► ByteTrack Tracker
                                │
                        Quality Assessment
                                │
              ┌─────────────────┴─────────────────┐
              ▼                                   ▼
      [Face Pipeline]                     [Re-ID Pipeline]
      - Face Detection                    - 512-dim Body Features
      - Embedding (histogram fallback)    - Spatial Correlation
      - Anti-Spoofing Liveness (heuristic)
              │                                   │
              └─────────────────┬─────────────────┘
                                ▼
                      Identity Fusion Engine
                                │
                      Authorization Engine ◄── Card Swipes / Door Policy
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
           [ALLOW]           [DENY]        [ALERT / REVIEW]
              │                 │                 │
              └─────────────────┼─────────────────┘
                                ▼
             Elasticsearch Store / Event Workers / UI
```

---

## Quick Start Guide

### 1. Run with Docker Compose (Recommended)

```bash
docker compose up --build
```

Access services:
- **Interactive Security Dashboard & UI**: [http://localhost:8000](http://localhost:8000)
- **Interactive OpenAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Prometheus Metrics**: [http://localhost:8000/metrics](http://localhost:8000/metrics)
- **Elasticsearch API**: [http://localhost:9200](http://localhost:9200)

---

### 2. Local Python Development Setup

1. Create and activate a Python virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```
2. Install dependencies (heavy: OpenCV + Ultralytics/YOLO — allow several minutes):
   ```bash
   pip install -r requirements.txt
   ```
3. Start the application:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

Elasticsearch and Redis are **optional locally**: if they are not running,
the app falls back to its in-memory store (see `app/repositories/elasticsearch.py`
and `app/repositories/redis.py`) and `/health/ready` reports them as
disconnected. With Docker Compose they run as services.

The app entrypoint is `app/main.py` (`uvicorn app.main:app`). `src/main.py`
is a separate, standalone synthetic camera sensor loop — it is not used by
the API or by Docker, so ignore it unless you want that loop on its own.
The dashboard is served from `app/static/index.html`; the duplicate
`index.html` that used to sit at the repo root has been removed.

---

## Running the Automated Test Suite

The test suite covers all 14 mandatory AI & access-control scenarios from Section 16:

```bash
pytest -v tests/
```

### Covered Test Cases:
| Test ID | Scenario | Expected Outcome |
|---|---|---|
| `test_case_01` | Correct card + correct employee biometric | `ALLOW` |
| `test_case_02` | Card/Person mismatch (Wrong person with card) | `ALERT` + Incident Created |
| `test_case_03` | Forgotten card via approved biometric-only | `ALLOW` |
| `test_case_04` | Unknown / unenrolled person | `DENY` |
| `test_case_05` | Presentation attack (Liveness failure) | `DENY` + Incident Created |
| `test_case_06` | One card swipe + two people crossing | `TAILGATING` Incident |
| `test_case_07` | Two legitimate badges swiped in window | No Alert (`Normal`) |
| `test_case_08` | Same person observed across 2 cameras | Unified `global_person_id` |
| `test_case_09` | Ambiguous similarity (nearest-match alone) | Fail-secure `DENY` |
| `test_case_10` | Camera frame/heartbeat timeout | `OFFLINE` + Maintenance Alert |
| `test_case_11` | Frozen identical video frames | `DEGRADED` Health State |
| `test_case_12` | Unauthorized zone boundary crossing | Security Incident Created |
| `test_case_13` | Deactivated employee swipe/biometric | `DENY` |
| `test_case_14` | Storage offline during access event | Resilient local buffer, no unsafe grant |

---

## API Surface Summary (all under `/api/v1`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/auth/token` | Obtain JWT access token for RBAC roles |
| `POST` | `/api/v1/employees` | Register new employee profile |
| `GET` | `/api/v1/employees` | List enrolled employees |
| `POST` | `/api/v1/employees/{id}/enrollment/face` | Enroll encrypted face biometric vector |
| `POST` | `/api/v1/employees/{id}/enrollment/person` | Enroll person Re-ID body feature vector |
| `POST` | `/api/v1/access/card-event` | Ingest physical card reader events |
| `POST` | `/api/v1/access/evaluate` | Multi-signal access authorization decision |
| `POST` | `/api/v1/access/crossing-event` | Ingest zone track crossing for tailgating |
| `POST` | `/api/v1/cameras` | Register RTSP camera feed |
| `GET` | `/api/v1/cameras/{id}/health` | Query camera FPS, latency, and stream health |
| `GET` | `/api/v1/dashboard/summary` | Aggregated real-time metrics & incident counts |
| `GET` | `/api/v1/audit/logs` | Query immutable security audit trail |

### Demo login accounts (development only)

`POST /api/v1/auth/token` with form fields `username` / `password`:

| Username | Password | Role |
|---|---|---|
| `admin` | `admin123` | SYSTEM_ADMIN |
| `sec_admin` | `secadmin123` | SECURITY_ADMIN |
| `operator` | `operator123` | SECURITY_OPERATOR |
| `maintenance` | `maint123` | MAINTENANCE_OPERATOR |
| `employee` | `emp123` | EMPLOYEE |
| `auditor` | `audit123` | AUDITOR |

These are plaintext demo defaults in `app/api/auth.py` — replace them with a
real user store and hashed passwords before any production use. The same
applies to the default JWT secret and biometric encryption key in
`configs/development.yaml` / `.env.example` and to the demo keys in
`docker-compose.yml`.

---

## Configuration

Configuration is managed via `configs/development.yaml` and `configs/production.yaml` with environment variable overrides:

```yaml
security:
  fail_secure: true
  require_liveness_for_biometric: true
identity:
  w_face: 0.35
  w_body: 0.15
  w_live: 0.20
  w_card: 0.15
  face_threshold: 0.65
  liveness_threshold: 0.70
tailgating:
  enabled: true
  authentication_window_seconds: 5.0
```

---

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.
