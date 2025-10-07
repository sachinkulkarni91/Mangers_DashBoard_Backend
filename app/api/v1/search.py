from fastapi import APIRouter, Depends, Query
from ...services.servicenow_client import get_client, ServiceNowClient
from ...schemas.search import UserSearchResults, LocationSearchResults
from typing import Optional, List

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/users", response_model=UserSearchResults)
async def search_users(q: str = Query(..., min_length=1, description="Search term"), limit: int = Query(20, le=100), fields: Optional[str] = Query(None, description="Comma separated list of fields to return. Use * for all."), client: ServiceNowClient = Depends(get_client)):
    field_list: Optional[List[str]] = None
    if fields is not None:
        parsed = [f.strip() for f in fields.split(',') if f.strip()]
        field_list = parsed if parsed else None
    records = await client.search_users(term=q, limit=limit, fields=field_list)
    return {"result": records}


@router.get("/locations", response_model=LocationSearchResults)
async def search_locations(q: str = Query(..., min_length=1, description="Search term"), limit: int = Query(20, le=100), fields: Optional[str] = Query(None, description="Comma separated list of fields to return. Use * for all."), client: ServiceNowClient = Depends(get_client)):
    field_list: Optional[List[str]] = None
    if fields is not None:
        parsed = [f.strip() for f in fields.split(',') if f.strip()]
        field_list = parsed if parsed else None
    records = await client.search_locations(term=q, limit=limit, fields=field_list)
    return {"result": records}
