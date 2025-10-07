from fastapi.testclient import TestClient
from app.main import app
from app.services.servicenow_client import ServiceNowClient, get_client
import pytest

class MockSetAssigneeClient(ServiceNowClient):  # type: ignore
    def __init__(self):
        pass

    async def update_incident(self, sys_id: str, payload):
        # Simulate success return (payload assigned_to will now be resolved sys_id from endpoint logic)
        return {"sys_id": sys_id, "assigned_to": payload.get("assigned_to"), "number": "INC0012345"}

    async def get_incident(self, number: str, fields=None):  # type: ignore
        # Map a fake incident number to a sys_id
        if number == 'INC1867021':
            return {"sys_id": "abcd1234efgh5678ijkl9012mnop3456", "number": number}
        return {}

    async def search_users(self, term: str, limit: int = 20, fields=None):  # type: ignore
        # Provide deterministic mock users
        users = [
            {"sys_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "name": "Renukumar P", "user_name": "renukumar.p"},
            {"sys_id": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "name": "John Smith", "user_name": "jsmith"},
            {"sys_id": "cccccccccccccccccccccccccccccccc", "name": "John Smith", "user_name": "john.smith2"},
        ]
        term_lower = term.lower()
        return [u for u in users if term_lower in u['name'].lower() or term_lower in u['user_name'].lower()][:limit]

async def _override_client():
    return MockSetAssigneeClient()

app.dependency_overrides[get_client] = _override_client
client = TestClient(app)

def test_set_assignee_partial_name():
    # partial "renu" should match unique Renukumar P
    resp = client.put("/api/v1/incidents/abcd1234efgh5678ijkl9012mnop3456/assignee", json={"assigned_to": "renu"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["assigned_to"] == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

def test_set_assignee_exact_name():
    resp = client.put("/api/v1/incidents/abcd1234efgh5678ijkl9012mnop3456/assignee", json={"assigned_to": "Renukumar P"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["assigned_to"] == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

def test_set_assignee_ambiguous_name():
    resp = client.put("/api/v1/incidents/abcd1234efgh5678ijkl9012mnop3456/assignee", json={"assigned_to": "John Smith"})
    assert resp.status_code == 409
    data = resp.json()
    assert "suggestions" in data["detail"]

def test_set_assignee_with_incident_number():
    resp = client.put("/api/v1/incidents/INC1867021/assignee", json={"assigned_to": "Renukumar P"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["assigned_to"] == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
