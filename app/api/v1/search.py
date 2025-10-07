from fastapi import APIRouter, Depends, Query
from ...services.servicenow_client import get_client, ServiceNowClient
from ...schemas.search import UserSearchResults, LocationSearchResults

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/users", response_model=UserSearchResults)
async def search_users(q: str = Query(..., min_length=1, description="Search term"), limit: int = Query(20, le=100), client: ServiceNowClient = Depends(get_client)):
    records = await client.search_users(term=q, limit=limit)
    return {"result": records}


@router.get("/locations", response_model=LocationSearchResults)
async def search_locations(q: str = Query(..., min_length=1, description="Search term"), limit: int = Query(20, le=100), client: ServiceNowClient = Depends(get_client)):
    records = await client.search_locations(term=q, limit=limit)
    return {"result": records}
