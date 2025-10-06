from app.services.servicenow_client import ServiceNowClient

async def test_normalize_record():
    client = ServiceNowClient()
    sample = {
        "number": "INC0012345",
        "assignment_group": {"display_value": "Global Support", "link": "https://x"},
        "caller_id": {"displayValue": "John Doe", "link": "https://y"},
        "short_description": "Test"
    }
    norm = client._normalize_record(sample)  # type: ignore (intentionally using internal)
    assert norm["assignment_group"] == "Global Support"
    assert norm["caller_id"] == "John Doe"
    assert norm["short_description"] == "Test"
