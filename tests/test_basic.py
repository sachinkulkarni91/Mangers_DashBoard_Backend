import os
from app.core.config import get_settings
from fastapi.testclient import TestClient
from app.main import app

def test_settings_defaults(monkeypatch):
    monkeypatch.setenv('SERVICENOW_INSTANCE','example.service-now.com')
    monkeypatch.setenv('SERVICENOW_USERNAME','user')
    monkeypatch.setenv('SERVICENOW_PASSWORD','pass')
    settings = get_settings()
    assert settings.servicENow_instance == 'example.service-now.com'

client = TestClient(app)

def test_health():
    resp = client.get('/health')
    assert resp.status_code == 200
    assert resp.json()['status'] == 'ok'
