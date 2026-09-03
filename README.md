# P-002: Intelligent Office Access Management System

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

An enterprise-grade, multi-camera AI security platform that authenticates office access through **multi-signal biometric fusion**, card-event correlation, presentation attack liveness detection, cross-camera person Re-ID, physical movement analytics, and fail-secure authorization rules.

```
CARD + BIOMETRIC IDENTITY + LIVENESS + PERSON RE-ID + AUTHORIZATION + PHYSICAL MOVEMENT ANALYTICS = INTELLIGENT ACCESS DECISION
```

---

## Key Features

1. **Multi-Signal Identity Fusion Engine (§8)**:
   - Evaluates weighted inputs from Face Recognition (ArcFace), Body/Person Re-ID, Anti-Spoofing Liveness, Access Card consistency, and Spatio-temporal context.
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
      - ArcFace Embedding                 - Spatial Correlation
      - Anti-Spoofing Liveness
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
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the application:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

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

## API Surface Summary (`/api/v1`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/token` | Obtain JWT access token for RBAC roles |
| `POST` | `/employees` | Register new employee profile |
| `GET` | `/employees` | List enrolled employees |
| `POST` | `/employees/{id}/enrollment/face` | Enroll encrypted face biometric vector |
| `POST` | `/employees/{id}/enrollment/person` | Enroll person Re-ID body feature vector |
| `POST` | `/access/card-event` | Ingest physical card reader events |
| `POST` | `/access/evaluate` | Multi-signal access authorization decision |
| `POST` | `/access/crossing-event` | Ingest zone track crossing for tailgating |
| `POST` | `/cameras` | Register RTSP camera feed |
| `GET` | `/cameras/{id}/health` | Query camera FPS, latency, and stream health |
| `GET` | `/dashboard/summary` | Aggregated real-time metrics & incident counts |
| `GET` | `/audit/logs` | Query immutable security audit trail |

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
