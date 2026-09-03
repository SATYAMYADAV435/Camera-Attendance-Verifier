from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional
from app.access_control.policy_engine import policy_engine
from app.ai.face import face_engine
from app.ai.fusion import fusion_engine
from app.ai.reid import reid_engine
from app.core.config import settings
from app.core.logging import ACCESS_DECISIONS_TOTAL, CARD_MISMATCH_TOTAL, logger
from app.core.security import biometric_crypto
from app.models.access_event import (
    AccessDecision,
    AccessEvaluationRequest,
    AccessEvaluationResponse,
    AuthMethod,
    ConfidenceTier,
)
from app.models.employee import Employee
from app.models.incident import IncidentSeverity, IncidentType, SecurityIncident
from app.models.policy import DoorPolicy
from app.repositories.elasticsearch import es_repo

class AccessDecisionEngine:
    async def evaluate_access(
        self,
        request: AccessEvaluationRequest,
        door_policy: Optional[DoorPolicy] = None
    ) -> AccessEvaluationResponse:
        event_id = str(uuid.uuid4())
        door_id = request.door_id
        pol = door_policy or policy_engine.default_policy

        # Step 1: Identify Card Owner (if card provided)
        card_employee: Optional[Employee] = None
        if request.card_id:
            raw_emp = await es_repo.find_employee_by_card(request.card_id)
            if raw_emp:
                card_employee = Employee(**raw_emp)

        # Step 2: Biometric Matching (Face & Body)
        matched_employee: Optional[Employee] = None
        face_sim_score = 0.0
        body_sim_score = 0.0

        if request.face_embedding:
            candidates = await es_repo.search_nearest_face_embedding(request.face_embedding, top_k=1)
            if candidates:
                top_candidate = candidates[0]
                if top_candidate["similarity"] >= settings.identity.face_threshold:
                    face_sim_score = top_candidate["similarity"]
                    matched_employee = Employee(**top_candidate["employee"])
                else:
                    face_sim_score = top_candidate["similarity"]

        # Step 3: Determine Body Re-ID similarity against candidate
        target_emp = matched_employee or card_employee
        if target_emp and request.body_embedding and target_emp.encrypted_body_embedding:
            try:
                enrolled_body_vec = biometric_crypto.decrypt_vector(target_emp.encrypted_body_embedding)
                body_sim_score = reid_engine.cosine_similarity(request.body_embedding, enrolled_body_vec)
            except Exception:
                body_sim_score = 0.0

        # Step 4: Determine Card vs Person Consistency
        card_consistency = 0.0
        is_mismatch = False

        if request.card_id and matched_employee:
            if card_employee and card_employee.employee_id == matched_employee.employee_id:
                card_consistency = 1.0
            else:
                # Mismatch detected: Card owner != Face identity
                card_consistency = 0.0
                is_mismatch = True
        elif request.card_id and not matched_employee:
            # Card presented, face unknown or not visible
            card_consistency = 0.5
        elif not request.card_id and matched_employee:
            # Biometric-only
            card_consistency = 1.0

        # Step 5: Liveness Validation
        liveness_val = request.liveness_score if request.liveness_score is not None else 1.0
        if pol.require_liveness and request.liveness_score is not None:
            if request.liveness_score < settings.identity.liveness_threshold:
                # Potential presentation attack
                logger.warning("Liveness verification failed for access request", score=request.liveness_score)

        # Step 6: Multi-Signal Identity Fusion
        final_score, confidence_tier, score_breakdown = fusion_engine.compute_fusion_score(
            face_score=face_sim_score,
            body_score=body_sim_score,
            liveness_score=liveness_val,
            card_consistency=card_consistency,
            temporal_consistency=1.0,
            camera_context=1.0,
        )

        # Step 7: Determine Authentication Method
        if request.card_id and matched_employee:
            auth_method = AuthMethod.CARD_AND_BIOMETRIC
        elif request.card_id:
            auth_method = AuthMethod.CARD_ONLY
        elif matched_employee:
            auth_method = AuthMethod.BIOMETRIC_ONLY
        else:
            auth_method = AuthMethod.CARD_ONLY

        # Step 8: Authorization Logic & Fail-Secure Policy
        decision = AccessDecision.DENY
        reason = "ACCESS_DENIED_UNKNOWN_IDENTITY"
        active_subject = matched_employee or card_employee

        # Check for card/person mismatch first
        if is_mismatch:
            CARD_MISMATCH_TOTAL.labels(door_id=door_id).inc()
            decision = AccessDecision.ALERT
            reason = f"CARD_PERSON_MISMATCH: Card owned by {card_employee.name if card_employee else 'Unknown'} but face matches {matched_employee.name}"
            # Record security incident
            incident = SecurityIncident(
                incident_id=f"INC-{uuid.uuid4().hex[:8].upper()}",
                incident_type=IncidentType.CARD_PERSON_MISMATCH,
                severity=IncidentSeverity.CRITICAL,
                camera_id=request.camera_id,
                door_id=door_id,
                employee_id=card_employee.employee_id if card_employee else None,
                card_id=request.card_id,
                description=reason,
                evidence=score_breakdown,
            )
            await es_repo.index_document("security_incidents", incident.incident_id, incident.model_dump(mode="json"))

        # Check liveness failure on biometric flow
        elif pol.require_liveness and request.liveness_score is not None and request.liveness_score < settings.identity.liveness_threshold:
            decision = AccessDecision.DENY
            reason = f"LIVENESS_FAILED: Spoof attack or uncertain liveness (score={request.liveness_score:.2f})"
            incident = SecurityIncident(
                incident_id=f"INC-{uuid.uuid4().hex[:8].upper()}",
                incident_type=IncidentType.SPOOFING_ATTEMPT,
                severity=IncidentSeverity.HIGH,
                camera_id=request.camera_id,
                door_id=door_id,
                employee_id=active_subject.employee_id if active_subject else None,
                description=reason,
                evidence=score_breakdown,
            )
            await es_repo.index_document("security_incidents", incident.incident_id, incident.model_dump(mode="json"))

        # Check cardless policy if no card presented
        elif not request.card_id and not pol.allow_cardless_biometric:
            decision = AccessDecision.DENY
            reason = "CARDLESS_BIOMETRIC_NOT_ALLOWED_BY_DOOR_POLICY"

        # Check high security two-factor policy
        elif pol.require_card_and_biometric and (not request.card_id or not matched_employee):
            decision = AccessDecision.DENY
            reason = "TWO_FACTOR_REQUIRED: Both card and biometric face verification are required for this door."

        elif active_subject:
            # Evaluate Door Access Policy
            policy_ok, policy_reason = policy_engine.evaluate_policy(active_subject, pol, request.timestamp)
            if not policy_ok:
                decision = AccessDecision.DENY
                reason = f"POLICY_VIOLATION: {policy_reason}"
            else:
                # Check confidence tier
                if confidence_tier == ConfidenceTier.HIGH:
                    decision = AccessDecision.ALLOW
                    reason = "AUTHENTICATION_SUCCESS"
                elif confidence_tier == ConfidenceTier.MEDIUM:
                    decision = AccessDecision.REVIEW
                    reason = f"MEDIUM_CONFIDENCE_REQUIRES_SECONDARY_FACTOR (Score={final_score:.2f})"
                else:
                    decision = AccessDecision.DENY
                    reason = f"INSUFFICIENT_CONFIDENCE_SCORE (Score={final_score:.2f})"
        else:
            decision = AccessDecision.DENY
            reason = "ACCESS_DENIED_UNKNOWN_OR_AMBIGUOUS_IDENTITY"

        # Log Prometheus Metric
        ACCESS_DECISIONS_TOTAL.labels(
            decision=decision.value,
            door_id=door_id,
            auth_method=auth_method.value
        ).inc()

        # Build response
        response = AccessEvaluationResponse(
            event_id=event_id,
            decision=decision,
            confidence_tier=confidence_tier,
            confidence_score=final_score,
            employee_id=active_subject.employee_id if active_subject else None,
            employee_name=active_subject.name if active_subject else None,
            auth_method=auth_method,
            reason=reason,
            door_id=door_id,
            camera_id=request.camera_id,
            score_breakdown=score_breakdown,
            timestamp=datetime.now(timezone.utc),
        )

        # Store in access_events repository
        await es_repo.index_document("access_events", event_id, response.model_dump(mode="json"))
        return response

decision_engine = AccessDecisionEngine()
