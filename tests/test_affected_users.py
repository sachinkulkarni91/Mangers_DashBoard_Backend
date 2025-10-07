from fastapi.testclient import TestClient
from app.main import app
from app.services.servicenow_client import ServiceNowClient, get_client

class MockAffectedUsersClient(ServiceNowClient):  # type: ignore
    def __init__(self):
        pass

    async def get_incident_affected_users(self, number: str, incident_fields=None, user_fields=None):
        # Simulate returning two users regardless of incident number
        base = [
            {"sys_id": "aaaa1111aaaa1111aaaa1111aaaa1111", "name": "Alice A", "user_name": "alice", "email": "alice@example.com"},
            {"sys_id": "bbbb2222bbbb2222bbbb2222bbbb2222", "name": "Bob B", "user_name": "bob", "email": "bob@example.com"},
        ]
        if user_fields and user_fields != ['*']:
            keep = set(user_fields) | {"sys_id"}
            filtered = []
            for u in base:
                filtered.append({k: v for k, v in u.items() if k in keep})
            return filtered
        return base

async def _override_client():
    return MockAffectedUsersClient()

app.dependency_overrides[get_client] = _override_client

client = TestClient(app)

def test_affected_users_all_fields():
    resp = client.get("/api/v1/incidents/INC0010001/affected-users")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["user_name"] == "alice"


def test_affected_users_field_filter():
    resp = client.get("/api/v1/incidents/INC0010001/affected-users", params={"user_fields": "name"})
    assert resp.status_code == 200
    data = resp.json()
    assert "name" in data[0]
    # Because response_model enforces optional fields, unspecified fields may appear as null.
    # Ensure that non-requested field user_name is null (filtered) instead of populated.
    assert data[0].get("user_name") in (None, "")
