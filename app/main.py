from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import httpx
from .core.logging_config import configure_logging
from .api.v1.incidents import router as incidents_router
from .api.v1.metrics import router as metrics_router
from .api.v1.search import router as search_router
from .core.config import get_settings

configure_logging()
settings = get_settings()

app = FastAPI(title="ServiceNow Dashboard API", version="0.1.0")
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def validate_settings():
    if settings.servicENow_instance.startswith("yourinstance"):
        logger.warning("SERVICENOW_INSTANCE appears to be placeholder; update .env to enable real connectivity.")


app.include_router(incidents_router, prefix="/api/v1")
app.include_router(metrics_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")

# Enable permissive CORS so the API is accessible from any origin.
# If you want to restrict access, replace `allow_origins=["*"]` with a list
# of allowed origins (e.g. ["https://example.com"]).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/health/servicenow")
async def health_servicenow():
    if settings.servicENow_instance.startswith("yourinstance"):
        return {"status": "placeholder", "detail": "Update SERVICENOW_INSTANCE for real check"}
    # Perform a lightweight HEAD request to instance root to verify DNS & TLS
    url = f"https://{settings.servicENow_instance}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
        return {"status": "reachable", "code": resp.status_code}
    except httpx.RequestError as e:
        return {"status": "unreachable", "error": str(e)}
