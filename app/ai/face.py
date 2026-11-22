from __future__ import annotations
import hashlib
import time
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np
from app.core.config import settings
from app.core.logging import AI_INFERENCE_LATENCY_SECONDS, logger

class FaceQualityAssessment:
    def __init__(
        self,
        min_face_size: int = 60,
        min_blur_score: float = 40.0,
        min_illumination: float = 30.0,
        max_illumination: float = 240.0,
    ):
        self.min_face_size = min_face_size
        self.min_blur_score = min_blur_score
        self.min_illumination = min_illumination
        self.max_illumination = max_illumination

    def assess_quality(self, face_crop: np.ndarray) -> Tuple[bool, float, Dict[str, Any]]:
        """Assesses face image quality based on resolution, blur, and lighting."""
        if face_crop is None or face_crop.size == 0:
            return False, 0.0, {"reason": "EMPTY_CROP"}

        h, w = face_crop.shape[:2]
        size_ok = h >= self.min_face_size and w >= self.min_face_size

        # Convert to grayscale for metric evaluations
        if len(face_crop.shape) == 3:
            gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = face_crop

        # 1. Blur Score (Laplacian variance)
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        blur_ok = laplacian_var >= self.min_blur_score

        # 2. Illumination Score (Mean intensity)
        mean_intensity = float(np.mean(gray))
        illum_ok = self.min_illumination <= mean_intensity <= self.max_illumination

        # Combined quality score in range [0.0, 1.0]
        size_factor = min(1.0, (w * h) / (120.0 * 120.0))
        blur_factor = min(1.0, laplacian_var / 200.0)
        illum_factor = 1.0 - abs(mean_intensity - 128.0) / 128.0
        overall_quality = float(np.clip(0.4 * size_factor + 0.4 * blur_factor + 0.2 * illum_factor, 0.0, 1.0))

        passed = size_ok and blur_ok and illum_ok and (overall_quality >= settings.identity.minimum_quality)
        metrics = {
            "size": f"{w}x{h}",
            "blur_score": laplacian_var,
            "mean_intensity": mean_intensity,
            "overall_quality": overall_quality,
            "size_ok": size_ok,
            "blur_ok": blur_ok,
            "illum_ok": illum_ok,
        }
        return passed, overall_quality, metrics

class FaceEmbeddingEngine:
    """512-dim embedding extractor.

    NOTE: this is NOT a real ArcFace/InsightFace model. No ONNX model
    weights are bundled, so it falls back to a deterministic
    colour-histogram feature vector (see extract_embedding). It is a
    demo-grade stand-in: do not present it as ArcFace recognition.
    """
    def __init__(self):
        self.quality_assessor = FaceQualityAssessment()
        self.embedding_dim = 512

    def extract_embedding(self, face_crop: np.ndarray) -> Tuple[Optional[List[float]], float, Dict[str, Any]]:
        start_time = time.time()
        passed, quality, metrics = self.quality_assessor.assess_quality(face_crop)
        
        if not passed:
            logger.debug("Face crop rejected by quality assessment", metrics=metrics)
            return None, quality, metrics

        # Generate a normalized 512-dim float embedding
        # In full production with ONNX model weights, run onnx session
        # Here we extract deterministic feature vector from crop texture & histogram
        resized = cv2.resize(face_crop, (112, 112))
        hist = cv2.calcHist([resized], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
        flattened = hist.flatten()
        
        # Ensure 512 dimensions and L2 normalization
        vec = np.zeros(self.embedding_dim, dtype=np.float32)
        vec[:min(len(flattened), self.embedding_dim)] = flattened[:self.embedding_dim]
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        else:
            vec[0] = 1.0

        duration = time.time() - start_time
        AI_INFERENCE_LATENCY_SECONDS.labels(component="face_embedding").observe(duration)
        return vec.tolist(), quality, metrics

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

face_engine = FaceEmbeddingEngine()
