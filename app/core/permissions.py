from __future__ import annotations
from enum import Enum
from typing import List, Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.security import decode_access_token

class UserRole(str, Enum):
    SYSTEM_ADMIN = "SYSTEM_ADMIN"
    SECURITY_ADMIN = "SECURITY_ADMIN"
    SECURITY_OPERATOR = "SECURITY_OPERATOR"
    MAINTENANCE_OPERATOR = "MAINTENANCE_OPERATOR"
    EMPLOYEE = "EMPLOYEE"
    AUDITOR = "AUDITOR"

# Role hierarchy / permissions map
ROLE_PERMISSIONS = {
    UserRole.SYSTEM_ADMIN: {
        "manage_system", "manage_config", "view_metrics", "view_audit_logs", "manage_cameras"
    },
    UserRole.SECURITY_ADMIN: {
        "manage_employees", "manage_enrollment", "manage_access_levels", "manage_policies",
        "manage_cameras", "view_audit_logs", "view_incidents", "resolve_incidents", "view_events",
        "evaluate_access"
    },
    UserRole.SECURITY_OPERATOR: {
        "view_events", "view_incidents", "acknowledge_incidents", "view_cameras", "view_employees",
        "evaluate_access", "view_dashboard"
    },
    UserRole.MAINTENANCE_OPERATOR: {
        "view_cameras", "manage_camera_health", "create_maintenance_ticket", "close_maintenance_ticket",
        "view_dashboard"
    },
    UserRole.EMPLOYEE: {
        "view_self", "request_re_enrollment", "view_own_history"
    },
    UserRole.AUDITOR: {
        "view_audit_logs", "view_events", "view_incidents", "view_employees_readonly", "view_reports"
    },
}

security_bearer = HTTPBearer(auto_error=False)

class AuthenticatedUser:
    def __init__(self, user_id: str, username: str, role: UserRole, employee_id: Optional[str] = None):
        self.user_id = user_id
        self.username = username
        self.role = role
        self.employee_id = employee_id

    def has_permission(self, permission: str) -> bool:
        return permission in ROLE_PERMISSIONS.get(self.role, set())

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
) -> AuthenticatedUser:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub") or payload.get("user_id")
    username = payload.get("username", "anonymous")
    role_str = payload.get("role", "EMPLOYEE")
    employee_id = payload.get("employee_id")

    try:
        role = UserRole(role_str)
    except ValueError:
        role = UserRole.EMPLOYEE

    return AuthenticatedUser(user_id=str(user_id), username=username, role=role, employee_id=employee_id)

def require_roles(allowed_roles: List[UserRole]):
    async def role_checker(current_user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User role '{current_user.role.value}' does not have permission to access this resource. Allowed: {[r.value for r in allowed_roles]}",
            )
        return current_user
    return role_checker
