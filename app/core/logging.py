from __future__ import annotations
import logging
import sys
from typing import Any, Dict
import structlog
from prometheus_client import Counter, Histogram, Gauge

# Prometheus Metrics Definitions (§22)
ACCESS_DECISIONS_TOTAL = Counter(
    "office_access_decisions_total",
    "Total access decisions by decision type and door",
    ["decision", "door_id", "auth_method"]
)

AI_INFERENCE_LATENCY_SECONDS = Histogram(
    "office_access_ai_inference_latency_seconds",
    "Latency of AI inference pipeline components",
    ["component"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0]
)

ACTIVE_CAMERAS_GAUGE = Gauge(
    "office_access_active_cameras",
    "Count of currently active/online cameras"
)

TAILGATING_INCIDENTS_TOTAL = Counter(
    "office_access_tailgating_incidents_total",
    "Total tailgating incidents detected",
    ["door_id", "severity"]
)

CARD_MISMATCH_TOTAL = Counter(
    "office_access_card_mismatches_total",
    "Total card vs biometric mismatches",
    ["door_id"]
)

CAMERA_FAILURES_TOTAL = Counter(
    "office_access_camera_failures_total",
    "Total camera failure events",
    ["camera_id", "failure_type"]
)

def configure_logging(environment: str = "development"):
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO if environment != "development" else logging.DEBUG,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer() if environment == "production" else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

logger = structlog.get_logger("intelligent-office-access")
