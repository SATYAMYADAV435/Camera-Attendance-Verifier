from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from app.core.logging import logger
from app.models.audit import AuditLogEntry
from app.repositories.elasticsearch import es_repo

class AuditService:
    """Immutable audit logging service ensuring all security-sensitive operations are recorded."""
    async def log_action(
        self,
        actor_id: str,
        actor_username: str,
        actor_role: str,
        action: str,
        target_type: str,
        target_id: Optional[str] = None,
        status: str = "SUCCESS",
        details: Optional[Dict[str, Any]] = None,
        ip_hash_or_reference: Optional[str] = None,
    ) -> AuditLogEntry:
        audit_id = f"AUD-{uuid.uuid4().hex[:10].upper()}"
        entry = AuditLogEntry(
            audit_id=audit_id,
            actor_id=actor_id,
            actor_username=actor_username,
            actor_role=actor_role,
            action=action,
            target_type=target_type,
            target_id=target_id,
            ip_hash_or_reference=ip_hash_or_reference,
            status=status,
            details=details or {},
            timestamp=datetime.now(timezone.utc),
        )
        
        # Write to persistent append-only store
        await es_repo.index_document("audit_logs", audit_id, entry.model_dump(mode="json"))
        logger.info(
            "Audit event logged",
            audit_id=audit_id,
            actor=actor_username,
            action=action,
            target=f"{target_type}:{target_id}",
            status=status
        )
        return entry

audit_service = AuditService()
