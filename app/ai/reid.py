from __future__ import annotations
import time
from typing import List, Optional, Tuple
import cv2
import numpy as np
from app.core.config import settings
from app.core.logging import AI_INFERENCE_LATENCY_SECONDS, logger

class PersonReIDEngine:
    """Person/Body Re-identification feature extractor for cross-camera correlation."""
    def __init__(self, embedding_dim: int = 512):
        self.embedding_dim = embedding_dim

    def extract_embedding(self, person_crop: np.ndarray) -> Optional[List[float]]:
        start_time = time.time()
        if person_crop is None or person_crop.size == 0:
            return None

        h, w = person_crop.shape[:2]
        if h < 80 or w < 30:
            return None

        # Standardize aspect ratio to 256x128 for body Re-ID
        resized = cv2.resize(person_crop, (128, 256))
        
        # Extract multi-region spatial color/texture representations (head, torso, legs)
        top_third = resized[0:85, :]
        mid_third = resized[85:170, :]
        bot_third = resized[170:256, :]

        hists = []
        for part in [top_third, mid_third, bot_third]:
            hist = cv2.calcHist([part], [0, 1, 2], None, [6, 6, 6], [0, 256, 0, 256, 0, 256])
            hists.append(hist.flatten())

        combined = np.concatenate(hists)
        vec = np.zeros(self.embedding_dim, dtype=np.float32)
        vec[:min(len(combined), self.embedding_dim)] = combined[:self.embedding_dim]
        
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        else:
            vec[0] = 1.0

        duration = time.time() - start_time
        AI_INFERENCE_LATENCY_SECONDS.labels(component="reid_embedding").observe(duration)
        return vec.tolist()

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

reid_engine = PersonReIDEngine()
