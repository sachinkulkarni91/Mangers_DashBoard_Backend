from fastapi.testclient import TestClient
from app.main import app
from app.services.servicenow_client import ServiceNowClient, get_client

class MockAssignClient(ServiceNowClient):  # type: ignore
    def __init__(self):
        pass

    async def search_assignable_users(self, term=None, assignment_group=None, limit: int = 20, fields=None):
        data = [
            {"sys_id": "1"*32, "name": "Alice Adams", "user_name": "aadams", "email": "alice@example.com"},
            {"sys_id": "2"*32, "name": "Bob Brown", "user_name": "bbrown", "email": "bob@example.com"},
            {"sys_id": "3"*32, "name": "Charlie Clark", "user_name": "cclark", "email": "charlie@example.com"},
        ]
        if term:
            t = term.lower()
            data = [u for u in data if t in u["name"].lower() or t in u["user_name"].lower()]
        if assignment_group:
            # simulate group returning only first two
            data = data[:2]
        data = data[:limit]
        if fields and fields != ['*']:
            keep = set(fields) | {"sys_id"}
            data = [{k: v for k, v in u.items() if k in keep} for u in data]
        return data

async def _override_client():
    return MockAssignClient()

app.dependency_overrides[get_client] = _override_client
client = TestClient(app)

def test_assignees_basic():
    r = client.get('/api/v1/search/assignees', params={'q': 'ali'})
    assert r.status_code == 200
    res = r.json()['result']
    assert len(res) == 1
    assert res[0]['user_name'] == 'aadams'

def test_assignees_group_filter_and_limit():
    r = client.get('/api/v1/search/assignees', params={'assignment_group': 'dummy', 'limit': 1})
    assert r.status_code == 200
    res = r.json()['result']
    assert len(res) == 1


def test_assignees_field_filter():
    r = client.get('/api/v1/search/assignees', params={'fields': 'name'} )
    assert r.status_code == 200
    res = r.json()['result']
    assert 'name' in res[0]
    # optional email may be omitted if not requested
    assert 'email' not in res[0] or res[0]['email'] is None
