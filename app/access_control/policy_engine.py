from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, Tuple
from app.core.config import settings
from app.models.employee import AccessLevel, Employee, EmployeeStatus
from app.models.policy import DoorPolicy, DoorSecurityLevel

class AccessPolicyEngine:
    def __init__(self):
        # Default policy for unconfigured doors
        self.default_policy = DoorPolicy(
            door_id="DEFAULT",
            door_name="Standard Office Door",
            zone_id="MAIN_LOBBY",
            security_level=DoorSecurityLevel.STANDARD,
            allow_cardless_biometric=settings.security.allow_cardless_access_default,
            require_card_and_biometric=False,
            require_liveness=settings.security.require_liveness_for_biometric,
            allowed_access_levels=["STANDARD", "EXECUTIVE", "ADMIN_FACILITY"],
        )

    def evaluate_policy(
        self,
        employee: Optional[Employee],
        policy: Optional[DoorPolicy],
        timestamp: Optional[datetime] = None
    ) -> Tuple[bool, str]:
        """Evaluates whether an employee satisfies the door policy, status, and time constraints."""
        ts = timestamp or datetime.now(timezone.utc)
        pol = policy or self.default_policy

        # 1. Employee status validation
        if not employee:
            return False, "EMPLOYEE_NOT_FOUND"

        if employee.status != EmployeeStatus.ACTIVE:
            return False, f"EMPLOYEE_STATUS_INVALID: {employee.status.value}"

        # 2. Access Level validation
        if employee.access_level.value not in pol.allowed_access_levels:
            return False, f"INSUFFICIENT_ACCESS_LEVEL: Required one of {pol.allowed_access_levels}, Employee has {employee.access_level.value}"

        # 3. Department restriction validation
        if pol.allowed_departments and employee.department not in pol.allowed_departments:
            return False, f"DEPARTMENT_NOT_AUTHORIZED: {employee.department}"

        # 4. Schedule and Time restriction validation
        if settings.security.enforce_time_restrictions and pol.schedule:
            weekday = ts.weekday()  # 0=Monday, 6=Sunday
            hour = ts.hour
            if weekday not in pol.schedule.allowed_days_of_week:
                return False, f"ACCESS_OUTSIDE_ALLOWED_DAYS: Day {weekday}"
            if not (pol.schedule.start_hour <= hour < pol.schedule.end_hour):
                return False, f"ACCESS_OUTSIDE_ALLOWED_HOURS: Hour {hour}"

        return True, "POLICY_PERMITTED"

policy_engine = AccessPolicyEngine()
