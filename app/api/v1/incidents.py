from fastapi import APIRouter, Depends, HTTPException, Query
from ...services.servicenow_client import get_client, ServiceNowClient
from ...schemas.incident import IncidentList, Incident, IncidentCreate, IncidentUpdate, AssigneeUpdate
from ...schemas.search import User
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

@router.put("/{sys_id}/assignee", response_model=Incident)
async def set_incident_assignee(sys_id: str, body: AssigneeUpdate, client: ServiceNowClient = Depends(get_client)):
    term = body.assigned_to.strip()
    # Detect if path param is an incident number (e.g., starts with INC and not 32 hex chars) and resolve to sys_id
    if not (len(sys_id) == 32 and all(c in '0123456789abcdef' for c in sys_id.lower())):
        # treat as number
        incident = await client.get_incident(sys_id, fields=['sys_id'])  # here sys_id is actually number
        if not incident or not incident.get('sys_id'):
            raise HTTPException(status_code=404, detail="Incident number not found")
        real_sys_id = incident['sys_id']
    else:
        real_sys_id = sys_id
    # Always treat input as a (partial) human name or user_name. We perform a limited search and then choose.
    try:
        candidates = await client.search_users(term=term, limit=25, fields=['sys_id','name','user_name','email'])
    except Exception:
        raise HTTPException(status_code=400, detail="Unable to search for assignee name")

    if not candidates:
        raise HTTPException(status_code=404, detail="No user found matching term")

    # Prioritize exact match on name, then exact on user_name, else if single result just use it, else ambiguous.
    lower_term = term.lower()
    exact_name = [u for u in candidates if (u.get('name') or '').lower() == lower_term]
    exact_uname = [u for u in candidates if (u.get('user_name') or '').lower() == lower_term]
    chosen = None
    if len(exact_name) == 1:
        chosen = exact_name[0]
    elif len(exact_uname) == 1 and not exact_name:
        chosen = exact_uname[0]
    elif len(candidates) == 1:
        chosen = candidates[0]
    else:
        # Ambiguous: return 409 with minimal suggestions
        suggestions = [
            {k: v for k, v in u.items() if k in {'sys_id','name','user_name','email'}} for u in candidates[:5]
        ]
        raise HTTPException(status_code=409, detail={"message": "Ambiguous name; refine search", "suggestions": suggestions})

    sys_id_target = chosen.get('sys_id')
    if not sys_id_target:
        raise HTTPException(status_code=500, detail="Resolved user missing sys_id")

    res = await client.update_incident(real_sys_id, {"assigned_to": sys_id_target})
    if not res:
        raise HTTPException(status_code=404, detail="Incident not found or update failed")
    return res

@router.get("/{number}/affected-users", response_model=list[User])
async def get_affected_users(
    number: str,
    user_fields: Optional[str] = Query(
        None,
        description="Comma-separated sys_user fields to return. Use * or omit for all.") ,
    client: ServiceNowClient = Depends(get_client)
):
    field_list: Optional[list[str]] = None
    if user_fields:
        parsed = [f.strip() for f in user_fields.split(',') if f.strip()]
        field_list = parsed if parsed else None
    users = await client.get_incident_affected_users(number=number, user_fields=field_list)
    return users
