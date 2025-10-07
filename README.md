# ServiceNow Dashboard FastAPI Backend

FastAPI application that proxies and aggregates data from ServiceNow for a dashboard similar to provided screenshots (incidents list, metrics tiles).

## Features
- List, retrieve, create, and update ServiceNow incidents (limited fields)
- Dashboard counts endpoint (sample queries; adjust to exact field names in your instance)
- Settings via environment variables / `.env`
- Structured project layout

## Environment Variables
See `.env.example` for all variables. Copy to `.env` and fill real credentials (never commit real secrets!).

| Variable | Description |
|----------|-------------|
| SERVICENOW_INSTANCE | yourinstance.service-now.com (without https://) |
| SERVICENOW_USERNAME | API user |
| SERVICENOW_PASSWORD | API user password |
| SERVICENOW_API_VERSION | Usually `now` |
| SERVICENOW_API_BASE_PATH | Defaults to `/api` (final base becomes https://instance/api/now). Change only if your instance differs. |
| SERVICENOW_TIMEOUT | Milliseconds timeout (e.g., 30000) |
| LOG_LEVEL | debug/info/warning/error |
| SERVICENOW_INCIDENT_FIELDS | Optional comma separated list of fields for list/detail |

## Install & Run (Windows PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env to add real credentials
uvicorn app.main:app --reload --port 8000
```
Open: http://127.0.0.1:8000/docs for interactive API docs.

Note: If you change `SERVICENOW_API_BASE_PATH` or `SERVICENOW_API_VERSION`, you must fully restart (not just reload) the server because settings are cached at process start.

## Endpoints
- `GET /health`
- `GET /health/servicenow` (light connectivity check; returns placeholder status if instance not configured)
- `GET /api/v1/incidents?limit=20&offset=0&q=encodedQuery`
- `GET /api/v1/incidents/{number}`
- `POST /api/v1/incidents` (create)
- `PATCH /api/v1/incidents/{sys_id}` (update)
 - `PUT /api/v1/incidents/{sys_id}/assignee` (set/replace assignee; body: {"assigned_to": "<user name or partial>"})
	 - Provide a partial or full user display name (or user_name); backend searches and resolves.
	 - Selection priority: exact name match > exact user_name match > single candidate > otherwise 409 with top 5 suggestions.
	 - 404 if nothing matches.
- `GET /api/v1/metrics/counts`
- `GET /api/v1/search/users?q=term&limit=20&fields=field1,field2` (user search; omit `fields` or set to `*` for all available table fields)
- `GET /api/v1/search/locations?q=term&limit=20&fields=field1,field2` (location search; omit `fields` or set to `*` for all)
 - `GET /api/v1/incidents/{number}/affected-users?user_fields=field1,field2` (derive affected users from incident user-related fields; omit `user_fields` or use `*` for all)

### Search Endpoint Field Control
For the search endpoints, previously a fixed subset of fields was returned. Now:
* If you do not pass `fields`, the backend will NOT restrict `sysparm_fields`, so ServiceNow returns all default readable fields for that table.
* If you pass `fields=field1,field2`, only those fields are requested from ServiceNow.
* If you pass `fields=*`, it's treated the same as omitting the parameter (all fields).

The response Pydantic models allow additional unexpected fields (`extra=allow`) so expanded data will be serialized without errors.

### Affected Users Derivation
The endpoint `/api/v1/incidents/{number}/affected-users` gathers unique user sys_ids from these incident fields (if present):
`caller_id, opened_by, requested_by, assigned_to, closed_by, watch_list, additional_assignee_list, u_affected_user, u_affected_users`.

It then queries `sys_user` for those ids. Provide `user_fields` to limit returned user attributes; omit or set `*` for all available fields. Optional fields not requested may appear as null due to schema shape.

## Adjusting Queries
The dashboard counts use placeholder query filters in `ServiceNowClient.get_dashboard_counts`. Update to reflect correct fields for SLA breach, at risk, etc. Use ServiceNow encoded queries (caret `^` separators). For counts we rely on header `X-Total-Count`; ensure your instance returns it (sometimes need `sysparm_count=true` or use aggregate API instead).

## Testing
```powershell
pytest -q
```

## Troubleshooting
### DNS / Connection Errors (e.g. `httpx.ConnectError: [Errno 11001] getaddrinfo failed`)
Cause: Hostname cannot be resolved. Most common when `SERVICENOW_INSTANCE` is still the placeholder (`yourinstance.service-now.com`) or there's a typo.

Steps:
1. Verify `.env` has the real instance (e.g. `companydev.service-now.com`). No protocol prefix.
2. Restart the server after changes (the settings are cached).
3. Visit `GET /health/servicenow` to confirm reachability.
4. If behind a proxy, set `HTTP_PROXY` / `HTTPS_PROXY` env vars before launching uvicorn.
5. If you receive a 502 gateway error from our API, check server logs for the underlying ServiceNow error.

### 502 Bad Gateway from API
We wrap network and HTTP-level errors. Typical fields:
```json
{"detail": {"error": "ServiceNowConnection", "message": "Unable to connect ..."}}
```
Action: Confirm credentials, network access, and that the user has table read rights.

### Empty Counts
The placeholder queries may not match your fields. Adjust `ServiceNowClient.get_dashboard_counts` queries to your environment (e.g., replace `u_sla_breached`).

## Security Notice
DO NOT hardcode or commit real credentials. Use `.env` only locally or a secure secret store in production.

## Next Enhancements
- Parallelize count queries with `asyncio.gather`
- Add caching (e.g. in-memory TTL) for metrics
- Pagination metadata (total count) for incidents
- Improved error handling & retries/backoff
- OAuth / Basic auth abstraction, token-based client
- Field mapping layer to control output shape
- WebSocket push for live updates
- Rate limiting & request validation
- Add CI pipeline and linting (ruff, mypy)

## Disclaimer
This is a starter implementation. You must tailor queries, fields, and security controls for your specific ServiceNow environment and compliance requirements.
