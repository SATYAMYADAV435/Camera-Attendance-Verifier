from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.permissions import AuthenticatedUser, UserRole, get_current_user, require_roles
from app.models.employee import (
    EmployeeCreate,
    EmployeePublic,
    EmployeeUpdate,
    FaceEnrollmentRequest,
    PersonReidEnrollmentRequest,
)
from app.services.employee_service import employee_service

router = APIRouter(prefix="/employees", tags=["Employees & Enrollment"])

@router.post("", response_model=EmployeePublic, status_code=status.HTTP_201_CREATED)
async def create_employee(
    employee_in: EmployeeCreate,
    current_user: AuthenticatedUser = Depends(require_roles([UserRole.SECURITY_ADMIN, UserRole.SYSTEM_ADMIN])),
):
    return await employee_service.create_employee(
        employee_in,
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        actor_username=current_user.username,
    )

@router.get("", response_model=List[EmployeePublic])
async def list_employees(
    limit: int = 100,
    current_user: AuthenticatedUser = Depends(require_roles([
        UserRole.SECURITY_ADMIN, UserRole.SECURITY_OPERATOR, UserRole.SYSTEM_ADMIN, UserRole.AUDITOR
    ])),
):
    return await employee_service.list_employees(limit=limit)

@router.get("/{employee_id}", response_model=EmployeePublic)
async def get_employee(
    employee_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    # Allow employee to view self, otherwise require operator/admin/auditor
    if current_user.role == UserRole.EMPLOYEE and current_user.employee_id != employee_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    emp = await employee_service.get_employee(employee_id)
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return emp

@router.patch("/{employee_id}", response_model=EmployeePublic)
async def update_employee(
    employee_id: str,
    update_in: EmployeeUpdate,
    current_user: AuthenticatedUser = Depends(require_roles([UserRole.SECURITY_ADMIN, UserRole.SYSTEM_ADMIN])),
):
    emp = await employee_service.update_employee(
        employee_id,
        update_in,
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        actor_username=current_user.username,
    )
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return emp

@router.delete("/{employee_id}")
async def deactivate_employee(
    employee_id: str,
    current_user: AuthenticatedUser = Depends(require_roles([UserRole.SECURITY_ADMIN, UserRole.SYSTEM_ADMIN])),
):
    success = await employee_service.deactivate_employee(
        employee_id,
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        actor_username=current_user.username,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return {"status": "DEACTIVATED", "employee_id": employee_id}

# Enrollment Sub-routes
@router.post("/{employee_id}/enrollment/face")
async def enroll_face_biometric(
    employee_id: str,
    request: FaceEnrollmentRequest,
    current_user: AuthenticatedUser = Depends(require_roles([UserRole.SECURITY_ADMIN])),
):
    success, reason, metrics = await employee_service.enroll_face(
        employee_id=employee_id,
        image_base64=request.image_base64,
        raw_embedding=request.raw_embedding,
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        actor_username=current_user.username,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)
    return {"status": "SUCCESS", "message": reason, "metrics": metrics}

@router.post("/{employee_id}/enrollment/person")
async def enroll_person_reid_biometric(
    employee_id: str,
    request: PersonReidEnrollmentRequest,
    current_user: AuthenticatedUser = Depends(require_roles([UserRole.SECURITY_ADMIN])),
):
    success, reason = await employee_service.enroll_person_reid(
        employee_id=employee_id,
        image_base64=request.image_base64,
        raw_embedding=request.raw_embedding,
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        actor_username=current_user.username,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)
    return {"status": "SUCCESS", "message": reason}

@router.post("/{employee_id}/enrollment/revoke")
async def revoke_biometrics(
    employee_id: str,
    current_user: AuthenticatedUser = Depends(require_roles([UserRole.SECURITY_ADMIN])),
):
    success = await employee_service.revoke_biometrics(
        employee_id,
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        actor_username=current_user.username,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return {"status": "REVOKED", "employee_id": employee_id}
