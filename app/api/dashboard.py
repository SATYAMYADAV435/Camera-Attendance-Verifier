from __future__ import annotations
from typing import Any, Dict
from fastapi import APIRouter, Depends
from app.core.permissions import AuthenticatedUser, UserRole, require_roles
from app.repositories.elasticsearch import es_repo

router = APIRouter(prefix="/dashboard", tags=["Security Dashboard"])

@router.get("/summary")
async def get_dashboard_summary(
    current_user: AuthenticatedUser = Depends(require_roles([
        UserRole.SECURITY_ADMIN, UserRole.SECURITY_OPERATOR, UserRole.SYSTEM_ADMIN, UserRole.MAINTENANCE_OPERATOR, UserRole.AUDITOR
    ])),
) -> Dict[str, Any]:
    # Aggregations from repository stores
    cameras = await es_repo.search_documents("cameras", limit=500)
    online_cameras = sum(1 for c in cameras if c.get("status") == "ONLINE")
    total_cameras = len(cameras)

    events = await es_repo.search_documents("access_events", limit=1000, sort_field="timestamp")
    granted_count = sum(1 for e in events if e.get("decision") == "ALLOW")
    denied_count = sum(1 for e in events if e.get("decision") == "DENY")
    review_count = sum(1 for e in events if e.get("decision") == "REVIEW")
    alert_count = sum(1 for e in events if e.get("decision") == "ALERT")

    incidents = await es_repo.search_documents("security_incidents", limit=500, sort_field="detected_at")
    open_incidents = [i for i in incidents if i.get("status") in ("NEW", "ACKNOWLEDGED", "INVESTIGATING")]
    
    tailgating_count = sum(1 for i in incidents if i.get("incident_type") == "TAILGATING")
    camera_failures = sum(1 for i in incidents if i.get("incident_type") == "CAMERA_FAILURE")
    mismatch_count = sum(1 for i in incidents if i.get("incident_type") == "CARD_PERSON_MISMATCH")
    spoof_count = sum(1 for i in incidents if i.get("incident_type") == "SPOOFING_ATTEMPT")

    return {
        "cameras": {
            "online": online_cameras,
            "total": total_cameras,
            "offline": total_cameras - online_cameras,
        },
        "access_metrics": {
            "total_evaluations": len(events),
            "granted": granted_count,
            "denied": denied_count,
            "review": review_count,
            "alert": alert_count,
            "success_rate": round(granted_count / len(events) * 100, 1) if events else 100.0,
        },
        "incident_counts": {
            "total_open": len(open_incidents),
            "tailgating": tailgating_count,
            "camera_failures": camera_failures,
            "card_person_mismatches": mismatch_count,
            "spoofing_attempts": spoof_count,
        },
        "recent_events": events[:10],
        "active_incidents": open_incidents[:10],
    }
