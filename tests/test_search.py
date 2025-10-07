from fastapi.testclient import TestClient
from app.main import app
from app.services.servicenow_client import ServiceNowClient, get_client
import asyncio


class MockServiceNowClient(ServiceNowClient):  # type: ignore
    def __init__(self):
        pass  # skip parent init

    async def search_users(self, term: str, limit: int = 20, fields=None):
        return [
            {"sys_id": "1", "name": "John Doe", "user_name": "jdoe", "email": "jdoe@example.com"},
            {"sys_id": "2", "name": "Jane Smith", "user_name": "jsmith", "email": "jsmith@example.com"},
        ][:limit]

    async def search_locations(self, term: str, limit: int = 20, fields=None):
        return [
            {"sys_id": "10", "name": "HQ", "city": "New York", "state": "NY", "country": "USA"},
            {"sys_id": "11", "name": "Branch", "city": "Austin", "state": "TX", "country": "USA"},
        ][:limit]


async def _override_client():  # async dependency
    return MockServiceNowClient()

app.dependency_overrides[get_client] = _override_client

client = TestClient(app)


def test_search_users():
    resp = client.get("/api/v1/search/users", params={"q": "jo", "limit": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert "result" in data
    assert len(data["result"]) == 1
    assert data["result"][0]["user_name"] == "jdoe"


def test_search_locations():
    resp = client.get("/api/v1/search/locations", params={"q": "h"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["result"]) == 2
    names = {r["name"] for r in data["result"]}
    assert {"HQ", "Branch"}.issubset(names)
