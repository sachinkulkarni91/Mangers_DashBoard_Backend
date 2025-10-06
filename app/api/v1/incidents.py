from fastapi import APIRouter, Depends, HTTPException, Query
from ...services.servicenow_client import get_client, ServiceNowClient
from ...schemas.incident import IncidentList, Incident, IncidentCreate, IncidentUpdate
from ...schemas.common import Message
from typing import Optional

router = APIRouter(prefix="/incidents", tags=["incidents"])

@router.get("/", response_model=IncidentList)
async def list_incidents(limit: int = Query(20, le=200), offset: int = 0, q: Optional[str] = Query(None, description="ServiceNow encoded query"), client: ServiceNowClient = Depends(get_client)):
    data = await client.list_incidents(limit=limit, offset=offset, query=q)
    # Pydantic model expects list of Incident.
    return data

@router.get("/{number}", response_model=Incident)
async def get_incident(number: str, client: ServiceNowClient = Depends(get_client)):
    data = await client.get_incident(number)
    if not data:
        raise HTTPException(status_code=404, detail="Incident not found")
    return data

@router.post("/", response_model=Incident)
async def create_incident(payload: IncidentCreate, client: ServiceNowClient = Depends(get_client)):
    res = await client.create_incident(payload.model_dump(exclude_none=True))
    return res

@router.patch("/{sys_id}", response_model=Incident)
async def update_incident(sys_id: str, payload: IncidentUpdate, client: ServiceNowClient = Depends(get_client)):
    res = await client.update_incident(sys_id, payload.model_dump(exclude_none=True))
    return res
