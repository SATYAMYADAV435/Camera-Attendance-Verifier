import pytest

@pytest.mark.asyncio
async def test_api_full_employee_and_access_lifecycle(async_client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Health check probes
    live_res = await async_client.get("/health/live")
    assert live_res.status_code == 200

    ready_res = await async_client.get("/health/ready")
    assert ready_res.status_code == 200

    # 2. Create Employee
    create_payload = {
        "employee_code": "INTEG-001",
        "name": "Integration Tester",
        "department": "Security Ops",
        "role": "Security Specialist",
        "access_level": "STANDARD",
        "card_id": "CARD-INTEG-99",
        "status": "ACTIVE"
    }
    create_res = await async_client.post("/api/v1/employees", headers=headers, json=create_payload)
    assert create_res.status_code == 201
    emp_data = create_res.json()
    emp_id = emp_data["employee_id"]

    # 3. Enroll Face Biometric
    dummy_vec = [0.0] * 512
    dummy_vec[10] = 1.0
    enroll_res = await async_client.post(
        f"/api/v1/employees/{emp_id}/enrollment/face",
        headers=headers,
        json={"raw_embedding": dummy_vec}
    )
    assert enroll_res.status_code == 200

    # 4. Evaluate Access with Card + Biometric
    eval_payload = {
        "door_id": "DOOR-MAIN-ENTRANCE",
        "card_id": "CARD-INTEG-99",
        "face_embedding": dummy_vec,
        "liveness_score": 0.95
    }
    eval_res = await async_client.post("/api/v1/access/evaluate", headers=headers, json=eval_payload)
    assert eval_res.status_code == 200
    eval_data = eval_res.json()
    assert eval_data["decision"] == "ALLOW"
    assert eval_data["employee_id"] == emp_id

    # 5. Check Dashboard Summary
    dash_res = await async_client.get("/api/v1/dashboard/summary", headers=headers)
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    assert dash_data["access_metrics"]["total_evaluations"] >= 1

    # 6. Check Audit Logs
    audit_res = await async_client.get("/api/v1/audit/logs", headers=headers)
    assert audit_res.status_code == 200
    audit_data = audit_res.json()
    assert len(audit_data) >= 1
