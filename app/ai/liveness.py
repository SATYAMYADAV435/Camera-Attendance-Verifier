from __future__ import annotations
import time
from typing import Dict, Tuple
import cv2
import numpy as np
from app.core.config import settings
from app.core.logging import AI_INFERENCE_LATENCY_SECONDS, logger

class LivenessDetector:
    """Presentation Attack Detection (PAD) verifying physical subject presence."""
    def __init__(self, threshold: Optional[float] = None):
        self.threshold = threshold or settings.identity.liveness_threshold

    def evaluate_liveness(self, face_crop: np.ndarray) -> Tuple[bool, float, Dict[str, float]]:
        """Evaluates face crop for screen replay, printed photo, and mask artifacts."""
        start_time = time.time()
        if face_crop is None or face_crop.size == 0:
            return False, 0.0, {"reason": "EMPTY_CROP"}

        h, w = face_crop.shape[:2]
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY) if len(face_crop.shape) == 3 else face_crop

        # 1. Texture analysis: high-frequency Fourier spectrum energy
        dft = cv2.dft(np.float32(gray), flags=cv2.DFT_COMPLEX_OUTPUT)
        dft_shift = np.fft.fftshift(dft)
        magnitude_spectrum = 20 * np.log(cv2.magnitude(dft_shift[:, :, 0], dft_shift[:, :, 1]) + 1e-5)
        
        # Calculate ratio of high-frequency components to low-frequency center
        cy, cx = h // 2, w // 2
        r = min(h, w) // 6
        center_energy = np.mean(magnitude_spectrum[max(0, cy-r):min(h, cy+r), max(0, cx-r):min(w, cx+r)])
        total_energy = np.mean(magnitude_spectrum)
        hf_ratio = float(total_energy / (center_energy + 1e-5))

        # 2. Color diversity and reflection analysis in YCrCb color space
        if len(face_crop.shape) == 3:
            ycrcb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2YCrCb)
            cr_std = float(np.std(ycrcb[:, :, 1]))
            cb_std = float(np.std(ycrcb[:, :, 2]))
            color_var_score = min(1.0, (cr_std + cb_std) / 25.0)
        else:
            color_var_score = 0.5

        # 3. Micro-texture gradient variance
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        grad_mag = np.sqrt(sobelx**2 + sobely**2)
        grad_score = float(min(1.0, np.var(grad_mag) / 800.0))

        # Combine into unified liveness confidence score [0.0, 1.0]
        liveness_score = float(np.clip(
            0.4 * color_var_score + 0.35 * grad_score + 0.25 * min(1.0, hf_ratio * 0.8),
            0.0, 1.0
        ))

        passed = liveness_score >= self.threshold
        metrics = {
            "liveness_score": liveness_score,
            "color_variation": color_var_score,
            "gradient_texture": grad_score,
            "threshold": self.threshold,
        }

        duration = time.time() - start_time
        AI_INFERENCE_LATENCY_SECONDS.labels(component="liveness_detection").observe(duration)
        return passed, liveness_score, metrics

liveness_detector = LivenessDetector()
