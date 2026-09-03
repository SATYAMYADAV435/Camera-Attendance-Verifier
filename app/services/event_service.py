from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.models.access_event import AccessEvent
from app.models.incident import IncidentStatus, SecurityIncident
from app.repositories.elasticsearch import es_repo
from app.services.audit_service import audit_service

class EventService:
    async def list_events(
        self,
        employee_id: Optional[str] = None,
        camera_id: Optional[str] = None,
        door_id: Optional[str] = None,
        decision: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        filters = {}
        if employee_id:
            filters["employee_id"] = employee_id
        if camera_id:
            filters["camera_id"] = camera_id
        if door_id:
            filters["door_id"] = door_id
        if decision:
            filters["decision"] = decision

        return await es_repo.search_documents("access_events", filters=filters, limit=limit, sort_field="timestamp")

    async def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        return await es_repo.get_document("access_events", event_id)

class IncidentService:
    async def list_incidents(
        self,
        incident_type: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        filters = {}
        if incident_type:
            filters["incident_type"] = incident_type
        if severity:
            filters["severity"] = severity
        if status:
            filters["status"] = status

        return await es_repo.search_documents("security_incidents", filters=filters, limit=limit, sort_field="detected_at")

    async def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        return await es_repo.get_document("security_incidents", incident_id)

    async def update_incident(
        self,
        incident_id: str,
        status: Optional[IncidentStatus] = None,
        assigned_to: Optional[str] = None,
        resolution: Optional[str] = None,
        actor_id: str = "SYSTEM",
        actor_role: str = "SECURITY_ADMIN",
        actor_username: str = "admin",
    ) -> Optional[Dict[str, Any]]:
        doc = await es_repo.get_document("security_incidents", incident_id)
        if not doc:
            return None

        if status:
            doc["status"] = status.value
            if status in (IncidentStatus.RESOLVED, IncidentStatus.FALSE_POSITIVE):
                doc["resolved_at"] = datetime.now(timezone.utc).isoformat()
        if assigned_to:
            doc["assigned_to"] = assigned_to
        if resolution:
            doc["resolution"] = resolution

        await es_repo.index_document("security_incidents", incident_id, doc)

        await audit_service.log_action(
            actor_id=actor_id,
            actor_username=actor_username,
            actor_role=actor_role,
            action="UPDATE_INCIDENT",
            target_type="INCIDENT",
            target_id=incident_id,
            details={"status": doc.get("status"), "resolution": resolution},
        )
        return doc

event_service = EventService()
incident_service = IncidentService()
