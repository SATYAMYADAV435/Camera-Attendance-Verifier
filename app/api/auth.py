from __future__ import annotations
from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from app.core.config import settings
from app.core.permissions import UserRole
from app.core.security import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user_id: str
    username: str
    role: UserRole

# Demo accounts with RBAC roles for development & testing ONLY.
# Passwords below are plaintext demo defaults (e.g. admin / admin123).
# They are NOT hashed and must be replaced with a real user store and
# hashed passwords before any production / network-exposed use.
DEMO_USERS = {
    "admin": {"user_id": "USR-ADMIN", "password_hash": "admin123", "role": UserRole.SYSTEM_ADMIN},
    "sec_admin": {"user_id": "USR-SEC-ADMIN", "password_hash": "secadmin123", "role": UserRole.SECURITY_ADMIN},
    "operator": {"user_id": "USR-OP", "password_hash": "operator123", "role": UserRole.SECURITY_OPERATOR},
    "maintenance": {"user_id": "USR-MAINT", "password_hash": "maint123", "role": UserRole.MAINTENANCE_OPERATOR},
    "employee": {"user_id": "USR-EMP", "password_hash": "emp123", "role": UserRole.EMPLOYEE},
    "auditor": {"user_id": "USR-AUD", "password_hash": "audit123", "role": UserRole.AUDITOR},
}

@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = DEMO_USERS.get(form_data.username)
    if not user or (form_data.password != user["password_hash"] and not verify_password(form_data.password, user["password_hash"])):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.system.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user["user_id"], "username": form_data.username, "role": user["role"].value},
        expires_delta=access_token_expires,
    )
    
    return TokenResponse(
        access_token=access_token,
        expires_in_minutes=settings.system.access_token_expire_minutes,
        user_id=user["user_id"],
        username=form_data.username,
        role=user["role"],
    )
