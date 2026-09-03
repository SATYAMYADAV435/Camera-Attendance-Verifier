import pytest
from app.core.permissions import AuthenticatedUser, UserRole

def test_rbac_roles_permissions():
    admin = AuthenticatedUser(user_id="U1", username="admin", role=UserRole.SECURITY_ADMIN)
    assert admin.has_permission("manage_employees") is True
    assert admin.has_permission("manage_enrollment") is True

    auditor = AuthenticatedUser(user_id="U2", username="auditor", role=UserRole.AUDITOR)
    assert auditor.has_permission("view_audit_logs") is True
    assert auditor.has_permission("manage_enrollment") is False

    maint = AuthenticatedUser(user_id="U3", username="maint", role=UserRole.MAINTENANCE_OPERATOR)
    assert maint.has_permission("create_maintenance_ticket") is True
    assert maint.has_permission("manage_employees") is False

@pytest.mark.asyncio
async def test_endpoint_rbac_access_denied_for_employee(async_client, employee_token):
    # Employee trying to enroll another employee must get 403 Forbidden
    res = await async_client.post(
        "/api/v1/employees/EMP-1001/enrollment/face",
        headers={"Authorization": f"Bearer {employee_token}"},
        json={"raw_embedding": [0.1] * 512}
    )
    assert res.status_code == 403

@pytest.mark.asyncio
async def test_endpoint_rbac_allowed_for_security_admin(async_client, admin_token):
    res = await async_client.get(
        "/api/v1/employees",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 200
