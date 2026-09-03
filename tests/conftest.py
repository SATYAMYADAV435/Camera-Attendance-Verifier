import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.security import create_access_token
from app.core.permissions import UserRole

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

@pytest.fixture
def admin_token():
    return create_access_token(data={"sub": "USR-TEST-ADMIN", "username": "admin", "role": UserRole.SECURITY_ADMIN.value})

@pytest.fixture
def operator_token():
    return create_access_token(data={"sub": "USR-TEST-OP", "username": "operator", "role": UserRole.SECURITY_OPERATOR.value})

@pytest.fixture
def employee_token():
    return create_access_token(data={"sub": "USR-TEST-EMP", "username": "employee", "role": UserRole.EMPLOYEE.value, "employee_id": "EMP-1001"})

@pytest.fixture
def auditor_token():
    return create_access_token(data={"sub": "USR-TEST-AUD", "username": "auditor", "role": UserRole.AUDITOR.value})
