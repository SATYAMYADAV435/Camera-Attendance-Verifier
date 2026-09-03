from __future__ import annotations
from typing import Dict, Tuple
from app.core.config import settings
from app.models.access_event import ConfidenceTier

class IdentityFusionEngine:
    """Multi-signal weighted fusion engine implementing the Section 8 identity fusion formula."""
    def __init__(self):
        self.w_face = settings.identity.w_face
        self.w_body = settings.identity.w_body
        self.w_live = settings.identity.w_live
        self.w_card = settings.identity.w_card
        self.w_time = settings.identity.w_time
        self.w_context = settings.identity.w_context

        self.high_thresh = settings.identity.high_confidence_threshold
        self.med_thresh = settings.identity.medium_confidence_threshold

    def compute_fusion_score(
        self,
        face_score: float = 0.0,
        body_score: float = 0.0,
        liveness_score: float = 0.0,
        card_consistency: float = 0.0,
        temporal_consistency: float = 1.0,
        camera_context: float = 1.0,
    ) -> Tuple[float, ConfidenceTier, Dict[str, float]]:
        """Computes weighted multi-signal fusion score and confidence tier."""
        # Weighted fusion sum
        raw_score = (
            self.w_face * float(face_score)
            + self.w_body * float(body_score)
            + self.w_live * float(liveness_score)
            + self.w_card * float(card_consistency)
            + self.w_time * float(temporal_consistency)
            + self.w_context * float(camera_context)
        )
        final_score = float(max(0.0, min(1.0, raw_score)))

        # Determine confidence tier
        if final_score >= self.high_thresh:
            tier = ConfidenceTier.HIGH
        elif final_score >= self.med_thresh:
            tier = ConfidenceTier.MEDIUM
        else:
            tier = ConfidenceTier.LOW

        breakdown = {
            "final_score": final_score,
            "face_component": round(self.w_face * face_score, 4),
            "body_component": round(self.w_body * body_score, 4),
            "liveness_component": round(self.w_live * liveness_score, 4),
            "card_component": round(self.w_card * card_consistency, 4),
            "temporal_component": round(self.w_time * temporal_consistency, 4),
            "context_component": round(self.w_context * camera_context, 4),
            "raw_face_score": face_score,
            "raw_body_score": body_score,
            "raw_liveness_score": liveness_score,
            "raw_card_consistency": card_consistency,
        }
        return final_score, tier, breakdown

fusion_engine = IdentityFusionEngine()
