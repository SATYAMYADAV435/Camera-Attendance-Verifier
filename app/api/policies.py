from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.permissions import AuthenticatedUser, UserRole, require_roles
from app.models.audit import AuditLogEntry
from app.models.policy import DoorPolicy
from app.repositories.elasticsearch import es_repo
from app.services.audit_service import audit_service

policies_router = APIRouter(prefix="/policies", tags=["Access Policies"])
audit_router = APIRouter(prefix="/audit", tags=["Audit Logs"])

# Policy Management
@policies_router.post("", response_model=DoorPolicy, status_code=status.HTTP_201_CREATED)
async def create_or_update_policy(
    policy: DoorPolicy,
    current_user: AuthenticatedUser = Depends(require_roles([UserRole.SECURITY_ADMIN, UserRole.SYSTEM_ADMIN])),
):
    await es_repo.index_document("policies", policy.door_id, policy.model_dump(mode="json"))
    await audit_service.log_action(
        actor_id=current_user.user_id,
        actor_username=current_user.username,
        actor_role=current_user.role.value,
        action="UPDATE_DOOR_POLICY",
        target_type="POLICY",
        target_id=policy.door_id,
        details=policy.model_dump(),
    )
    return policy

@policies_router.get("", response_model=List[DoorPolicy])
async def list_policies(
    current_user: AuthenticatedUser = Depends(require_roles([
        UserRole.SECURITY_ADMIN, UserRole.SECURITY_OPERATOR, UserRole.SYSTEM_ADMIN, UserRole.AUDITOR
    ])),
):
    docs = await es_repo.search_documents("policies", limit=100)
    return [DoorPolicy(**d) for d in docs]

@policies_router.get("/{door_id}", response_model=DoorPolicy)
async def get_policy(
    door_id: str,
    current_user: AuthenticatedUser = Depends(require_roles([
        UserRole.SECURITY_ADMIN, UserRole.SECURITY_OPERATOR, UserRole.SYSTEM_ADMIN, UserRole.AUDITOR
    ])),
):
    doc = await es_repo.get_document("policies", door_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found for door")
    return DoorPolicy(**doc)

# Audit Logs
@audit_router.get("/logs", response_model=List[AuditLogEntry])
async def list_audit_logs(
    actor_id: Optional[str] = None,
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    limit: int = 100,
    current_user: AuthenticatedUser = Depends(require_roles([
        UserRole.AUDITOR, UserRole.SECURITY_ADMIN, UserRole.SYSTEM_ADMIN
    ])),
):
    filters = {}
    if actor_id:
        filters["actor_id"] = actor_id
    if action:
        filters["action"] = action
    if target_type:
        filters["target_type"] = target_type

    docs = await es_repo.search_documents("audit_logs", filters=filters, limit=limit, sort_field="timestamp")
    return [AuditLogEntry(**d) for d in docs]
