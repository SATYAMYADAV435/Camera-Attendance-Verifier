from __future__ import annotations
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

class SystemConfig(BaseModel):
    environment: str = "development"
    app_name: str = "Intelligent Office Access Management System"
    debug: bool = True
    api_prefix: str = "/api/v1"
    secret_key: str = "dev-secret-key-32-bytes-minimum-security-required-12345"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

class SecurityConfig(BaseModel):
    fail_secure: bool = True
    require_liveness_for_biometric: bool = True
    allow_cardless_access_default: bool = True
    enforce_time_restrictions: bool = True
    biometric_encryption_key: str = "MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDE="  # 32-byte base64 default

class IdentityConfig(BaseModel):
    # Weights for fusion
    w_face: float = 0.35
    w_body: float = 0.15
    w_live: float = 0.20
    w_card: float = 0.15
    w_time: float = 0.08
    w_context: float = 0.07

    # Thresholds
    face_threshold: float = 0.65
    body_threshold: float = 0.60
    liveness_threshold: float = 0.70
    minimum_quality: float = 0.50

    # Decision tiers
    high_confidence_threshold: float = 0.75
    medium_confidence_threshold: float = 0.55

class TailgatingConfig(BaseModel):
    enabled: bool = True
    authentication_window_seconds: float = 5.0
    door_crossing_window_seconds: float = 4.0
    max_allowed_distance_pixels: float = 120.0

class MultiCameraConfig(BaseModel):
    enabled: bool = True
    reid_similarity_threshold: float = 0.65
    max_transit_time_seconds: float = 180.0
    min_transit_time_seconds: float = 1.0

class CameraConfig(BaseModel):
    heartbeat_timeout_seconds: float = 30.0
    failure_timeout_seconds: float = 60.0
    frozen_frame_detection: bool = True
    frozen_frame_threshold: int = 20
    blur_laplacian_threshold: float = 40.0
    default_fps: float = 30.0

class ElasticsearchConfig(BaseModel):
    hosts: List[str] = Field(default_factory=lambda: ["http://localhost:9200"])
    index_prefix: str = "office-access"
    enable_in_memory_fallback: bool = True

class RedisConfig(BaseModel):
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    enable_in_memory_fallback: bool = True

class RetentionConfig(BaseModel):
    access_events_days: int = 90
    observations_days: int = 14
    incidents_days: int = 365
    audit_logs_days: int = 730

class AppSettings(BaseSettings):
    system: SystemConfig = Field(default_factory=SystemConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    identity: IdentityConfig = Field(default_factory=IdentityConfig)
    tailgating: TailgatingConfig = Field(default_factory=TailgatingConfig)
    multi_camera: MultiCameraConfig = Field(default_factory=MultiCameraConfig)
    camera: CameraConfig = Field(default_factory=CameraConfig)
    elasticsearch: ElasticsearchConfig = Field(default_factory=ElasticsearchConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    retention: RetentionConfig = Field(default_factory=RetentionConfig)

    @classmethod
    def load_from_env_or_yaml(cls) -> "AppSettings":
        env = os.getenv("APP_ENV", "development").lower()
        config_path = Path("configs") / f"{env}.yaml"
        if not config_path.exists():
            config_path = Path("configs/development.yaml")

        data: Dict[str, Any] = {}
        if config_path.exists():
            try:
                raw_text = config_path.read_text(encoding="utf-8")
                # Resolve environment variable placeholders ${VAR:-default}
                def replace_env(match):
                    expr = match.group(1)
                    if ":-" in expr:
                        var_name, default_val = expr.split(":-", 1)
                        return os.getenv(var_name, default_val)
                    return os.getenv(expr, "")

                expanded = re.sub(r"\$\{([^}]+)\}", replace_env, raw_text)
                loaded = yaml.safe_load(expanded)
                if isinstance(loaded, dict):
                    data = loaded
            except Exception:
                data = {}

        return cls(**data)

settings = AppSettings.load_from_env_or_yaml()
