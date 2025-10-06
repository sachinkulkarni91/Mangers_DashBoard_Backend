from pydantic import BaseModel, Field
from typing import Optional, List

class IncidentBase(BaseModel):
    short_description: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    priority: Optional[str] = None
    state: Optional[str] = None
    assignment_group: Optional[str] = None
    assigned_to: Optional[str] = None

class IncidentCreate(IncidentBase):
    caller_id: Optional[str] = None

class IncidentUpdate(IncidentBase):
    pass

class Incident(IncidentBase):
    number: str
    sys_id: Optional[str] = None
    sys_created_on: Optional[str] = None
    sys_updated_on: Optional[str] = None

class IncidentList(BaseModel):
    result: List[Incident]

class DashboardCounts(BaseModel):
    open_p1: int = 0
    sla_breached: int = 0
    not_updated_24h: int = 0
    sla_at_risk: int = 0
    unassigned: int = 0
