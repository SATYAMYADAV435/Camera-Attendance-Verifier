from __future__ import annotations
import base64
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import cv2
import numpy as np
from app.ai.face import face_engine
from app.ai.reid import reid_engine
from app.core.logging import logger
from app.core.security import biometric_crypto
from app.models.employee import (
    Employee,
    EmployeeCreate,
    EmployeePublic,
    EmployeeStatus,
    EmployeeUpdate,
    EnrollmentStatus,
)
from app.repositories.elasticsearch import es_repo
from app.services.audit_service import audit_service

class EmployeeService:
    async def create_employee(self, emp_in: EmployeeCreate, actor_id: str, actor_role: str, actor_username: str) -> EmployeePublic:
        emp_id = f"EMP-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        
        employee = Employee(
            employee_id=emp_id,
            employee_code=emp_in.employee_code,
            name=emp_in.name,
            department=emp_in.department,
            role=emp_in.role,
            status=emp_in.status,
            access_level=emp_in.access_level,
            card_id=emp_in.card_id,
            created_at=now,
            updated_at=now,
        )

        # Store in ES
        doc = employee.model_dump(mode="json")
        await es_repo.index_document("employees", emp_id, doc)

        # Audit log
        await audit_service.log_action(
            actor_id=actor_id,
            actor_username=actor_username,
            actor_role=actor_role,
            action="CREATE_EMPLOYEE",
            target_type="EMPLOYEE",
            target_id=emp_id,
            details={"employee_code": emp_in.employee_code, "name": emp_in.name},
        )

        return EmployeePublic(**employee.model_dump())

    async def get_employee(self, employee_id: str) -> Optional[EmployeePublic]:
        doc = await es_repo.get_document("employees", employee_id)
        if not doc:
            return None
        return EmployeePublic(**doc)

    async def list_employees(self, limit: int = 100) -> List[EmployeePublic]:
        docs = await es_repo.search_documents("employees", limit=limit, sort_field="created_at")
        return [EmployeePublic(**d) for d in docs]

    async def update_employee(
        self, employee_id: str, emp_update: EmployeeUpdate, actor_id: str, actor_role: str, actor_username: str
    ) -> Optional[EmployeePublic]:
        doc = await es_repo.get_document("employees", employee_id)
        if not doc:
            return None

        update_dict = emp_update.model_dump(exclude_unset=True)
        for k, v in update_dict.items():
            if v is not None:
                doc[k] = v.value if hasattr(v, "value") else v
        
        doc["updated_at"] = datetime.now(timezone.utc).isoformat()
        await es_repo.index_document("employees", employee_id, doc)

        await audit_service.log_action(
            actor_id=actor_id,
            actor_username=actor_username,
            actor_role=actor_role,
            action="UPDATE_EMPLOYEE",
            target_type="EMPLOYEE",
            target_id=employee_id,
            details=update_dict,
        )

        return EmployeePublic(**doc)

    async def deactivate_employee(self, employee_id: str, actor_id: str, actor_role: str, actor_username: str) -> bool:
        """Deactivates employee (never hard deletes security history)."""
        doc = await es_repo.get_document("employees", employee_id)
        if not doc:
            return False

        doc["status"] = EmployeeStatus.INACTIVE.value
        doc["updated_at"] = datetime.now(timezone.utc).isoformat()
        await es_repo.index_document("employees", employee_id, doc)

        await audit_service.log_action(
            actor_id=actor_id,
            actor_username=actor_username,
            actor_role=actor_role,
            action="DEACTIVATE_EMPLOYEE",
            target_type="EMPLOYEE",
            target_id=employee_id,
            details={"new_status": "INACTIVE"},
        )
        return True

    async def enroll_face(
        self,
        employee_id: str,
        image_base64: Optional[str] = None,
        raw_embedding: Optional[List[float]] = None,
        actor_id: str = "ADMIN",
        actor_role: str = "SECURITY_ADMIN",
        actor_username: str = "admin",
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Extracts, validates quality, AES-256 encrypts and enrolls face embedding."""
        doc = await es_repo.get_document("employees", employee_id)
        if not doc:
            return False, "EMPLOYEE_NOT_FOUND", {}

        embedding_vector: Optional[List[float]] = None
        quality_metrics: Dict[str, Any] = {}

        if raw_embedding:
            # Normalize provided vector
            vec = np.array(raw_embedding, dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                embedding_vector = (vec / norm).tolist()
            else:
                embedding_vector = raw_embedding
            quality_metrics = {"quality": 1.0, "source": "DIRECT_VECTOR"}
        elif image_base64:
            try:
                img_data = base64.b64decode(image_base64)
                nparr = np.frombuffer(img_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                vec, quality, metrics = face_engine.extract_embedding(img)
                if vec is None:
                    return False, f"FACE_QUALITY_INSUFFICIENT: {metrics.get('reason', 'Quality check failed')}", metrics
                embedding_vector = vec
                quality_metrics = metrics
            except Exception as e:
                return False, f"IMAGE_DECODING_ERROR: {str(e)}", {}
        else:
            return False, "MISSING_IMAGE_OR_EMBEDDING", {}

        # Encrypt vector at rest with AES-256-GCM
        encrypted_b64 = biometric_crypto.encrypt_vector(embedding_vector)
        doc["encrypted_face_embedding"] = encrypted_b64
        # Cache raw in resilient ES repository for fast kNN matching in memory
        doc["face_embedding_raw"] = embedding_vector
        doc["face_enrollment_status"] = EnrollmentStatus.ENROLLED.value
        doc["enrollment_version"] = doc.get("enrollment_version", 1) + 1
        doc["updated_at"] = datetime.now(timezone.utc).isoformat()

        await es_repo.index_document("employees", employee_id, doc)

        await audit_service.log_action(
            actor_id=actor_id,
            actor_username=actor_username,
            actor_role=actor_role,
            action="ENROLL_FACE_BIOMETRIC",
            target_type="EMPLOYEE",
            target_id=employee_id,
            details={"quality_metrics": quality_metrics, "version": doc["enrollment_version"]},
        )

        return True, "FACE_ENROLLED_SUCCESSFULLY", quality_metrics

    async def enroll_person_reid(
        self,
        employee_id: str,
        image_base64: Optional[str] = None,
        raw_embedding: Optional[List[float]] = None,
        actor_id: str = "ADMIN",
        actor_role: str = "SECURITY_ADMIN",
        actor_username: str = "admin",
    ) -> Tuple[bool, str]:
        doc = await es_repo.get_document("employees", employee_id)
        if not doc:
            return False, "EMPLOYEE_NOT_FOUND"

        if raw_embedding:
            embedding_vector = raw_embedding
        elif image_base64:
            try:
                img_data = base64.b64decode(image_base64)
                nparr = np.frombuffer(img_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                vec = reid_engine.extract_embedding(img)
                if vec is None:
                    return False, "BODY_REID_CROP_TOO_SMALL"
                embedding_vector = vec
            except Exception as e:
                return False, f"IMAGE_DECODING_ERROR: {str(e)}"
        else:
            return False, "MISSING_IMAGE_OR_EMBEDDING"

        encrypted_b64 = biometric_crypto.encrypt_vector(embedding_vector)
        doc["encrypted_body_embedding"] = encrypted_b64
        doc["body_embedding_raw"] = embedding_vector
        doc["person_reid_status"] = EnrollmentStatus.ENROLLED.value
        doc["updated_at"] = datetime.now(timezone.utc).isoformat()

        await es_repo.index_document("employees", employee_id, doc)

        await audit_service.log_action(
            actor_id=actor_id,
            actor_username=actor_username,
            actor_role=actor_role,
            action="ENROLL_PERSON_REID",
            target_type="EMPLOYEE",
            target_id=employee_id,
        )
        return True, "PERSON_REID_ENROLLED_SUCCESSFULLY"

    async def revoke_biometrics(
        self, employee_id: str, actor_id: str, actor_role: str, actor_username: str
    ) -> bool:
        doc = await es_repo.get_document("employees", employee_id)
        if not doc:
            return False

        doc["encrypted_face_embedding"] = None
        doc["face_embedding_raw"] = None
        doc["encrypted_body_embedding"] = None
        doc["body_embedding_raw"] = None
        doc["face_enrollment_status"] = EnrollmentStatus.REVOKED.value
        doc["person_reid_status"] = EnrollmentStatus.REVOKED.value
        doc["updated_at"] = datetime.now(timezone.utc).isoformat()

        await es_repo.index_document("employees", employee_id, doc)

        await audit_service.log_action(
            actor_id=actor_id,
            actor_username=actor_username,
            actor_role=actor_role,
            action="REVOKE_BIOMETRICS",
            target_type="EMPLOYEE",
            target_id=employee_id,
        )
        return True

employee_service = EmployeeService()
