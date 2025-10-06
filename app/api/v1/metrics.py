from fastapi import APIRouter, Depends
from ...services.servicenow_client import get_client, ServiceNowClient
from ...schemas.incident import DashboardCounts

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.get("/counts", response_model=DashboardCounts)
async def get_counts(client: ServiceNowClient = Depends(get_client)):
    counts = await client.get_dashboard_counts()
    return counts
