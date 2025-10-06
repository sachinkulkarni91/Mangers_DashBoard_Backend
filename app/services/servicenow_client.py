import httpx
from typing import Any, Dict, List, Optional
from ..core.config import get_settings
import logging
from ..utils.exceptions import raise_gateway_error, ServiceNowConnectionError

logger = logging.getLogger(__name__)

class ServiceNowClient:
    def __init__(self):
        self.settings = get_settings()
        timeout_seconds = self.settings.servicENow_timeout / 1000.0
        self._client = httpx.AsyncClient(
            base_url=self.settings.base_url,
            timeout=timeout_seconds,
            auth=(self.settings.servicENow_username, self.settings.servicENow_password)
        )

    def _handle_redirect(self, resp: httpx.Response, context: str):
        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get('Location', '')
            logger.error(
                "ServiceNow unexpected redirect (%s) during %s -> %s | Base URL %s | Hint: Ensure base URL includes /api (current: %s) and credentials are Basic Auth user. If SSO is enforced, create an API user.",
                resp.status_code, context, location, self.settings.base_url, self.settings.base_url
            )
            raise_gateway_error(f"Unexpected redirect ({resp.status_code}). Check API base path or SSO settings.")

    async def close(self):
        await self._client.aclose()

    async def list_incidents(self, limit: int = 20, offset: int = 0, query: Optional[str] = None, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        params = {
            'sysparm_limit': str(limit),
            'sysparm_offset': str(offset),
            'sysparm_display_value': 'true',
        }
        if fields is None:
            fields = self.settings.get_incident_fields()
        params['sysparm_fields'] = ','.join(fields)
        if query:
            params['sysparm_query'] = query
        url = f"/table/incident"
        logger.debug(f"Fetching incidents with params {params}")
        try:
            resp = await self._client.get(url, params=params)
            self._handle_redirect(resp, "list incidents")
            resp.raise_for_status()
            data = resp.json()
            records = data.get('result', data)
            normalized = [self._normalize_record(r) for r in records]
            return {'result': normalized}
        except httpx.RequestError as e:
            logger.error(f"ServiceNow connection error listing incidents: {e}")
            raise_gateway_error("Unable to connect to ServiceNow (list incidents)")
        except httpx.HTTPStatusError as e:
            logger.error(f"ServiceNow HTTP error listing incidents: {e.response.status_code} {e.response.text}")
            raise_gateway_error(f"ServiceNow responded with status {e.response.status_code}")

    async def get_incident(self, number: str, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        # number is the human readable. Need to query by number.
        if fields is None:
            fields = self.settings.get_incident_fields()
        params = {
            'sysparm_query': f"number={number}",
            'sysparm_limit': '1',
            'sysparm_fields': ','.join(fields),
            'sysparm_display_value': 'true'
        }
        try:
            resp = await self._client.get('/table/incident', params=params)
            self._handle_redirect(resp, f"get incident {number}")
            resp.raise_for_status()
            res = resp.json().get('result', [])
            if not res:
                return {}
            return self._normalize_record(res[0])
        except httpx.RequestError as e:
            logger.error(f"ServiceNow connection error get incident {number}: {e}")
            raise_gateway_error("Unable to connect to ServiceNow (get incident)")
        except httpx.HTTPStatusError as e:
            logger.error(f"ServiceNow HTTP error get incident {number}: {e.response.status_code} {e.response.text}")
            raise_gateway_error(f"ServiceNow responded with status {e.response.status_code}")

    async def create_incident(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            resp = await self._client.post('/table/incident', json=payload)
            self._handle_redirect(resp, "create incident")
            resp.raise_for_status()
            return resp.json().get('result', {})
        except httpx.RequestError as e:
            logger.error(f"ServiceNow connection error create incident: {e}")
            raise_gateway_error("Unable to connect to ServiceNow (create incident)")
        except httpx.HTTPStatusError as e:
            logger.error(f"ServiceNow HTTP error create incident: {e.response.status_code} {e.response.text}")
            raise_gateway_error(f"ServiceNow responded with status {e.response.status_code}")

    async def update_incident(self, sys_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            resp = await self._client.patch(f'/table/incident/{sys_id}', json=payload)
            self._handle_redirect(resp, f"update incident {sys_id}")
            resp.raise_for_status()
            return resp.json().get('result', {})
        except httpx.RequestError as e:
            logger.error(f"ServiceNow connection error update incident {sys_id}: {e}")
            raise_gateway_error("Unable to connect to ServiceNow (update incident)")
        except httpx.HTTPStatusError as e:
            logger.error(f"ServiceNow HTTP error update incident {sys_id}: {e.response.status_code} {e.response.text}")
            raise_gateway_error(f"ServiceNow responded with status {e.response.status_code}")

    async def get_dashboard_counts(self) -> Dict[str, int]:
        # Example counts similar to screenshot: open P1, breached SLA, not updated 24h, incidents at risk, my incidents, unassigned
        # This uses multiple queries; optimize later with parallel tasks.
        queries = {
            'open_p1': 'priority=1^stateNOT IN6,7',
            'sla_breached': 'u_sla_breached=true',  # placeholder - adjust field names
            'not_updated_24h': 'sys_updated_onRELATIVELE@dayofweek@ago@1',
            'sla_at_risk': 'u_sla_at_risk=true',
            'unassigned': 'assigned_toISEMPTY^stateNOT IN6,7',
        }
        results: Dict[str,int] = {}
        for key, q in queries.items():
            params = {'sysparm_query': q, 'sysparm_count': 'true'}
            try:
                resp = await self._client.get('/table/incident', params=params)
                self._handle_redirect(resp, f"count {key}")
                if resp.status_code == 200:
                    try:
                        results[key] = int(resp.headers.get('X-Total-Count', '0'))
                    except ValueError:
                        results[key] = 0
                else:
                    results[key] = 0
            except httpx.RequestError as e:
                logger.error(f"ServiceNow connection error counts {key}: {e}")
                results[key] = 0
            except httpx.HTTPStatusError as e:
                logger.error(f"ServiceNow HTTP error counts {key}: {e.response.status_code} {e.response.text}")
                results[key] = 0
        return results

    # ----------------- internal helpers -----------------
    def _normalize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten reference field objects (with display_value/link) to just the display_value string.
        ServiceNow returns objects when sysparm_display_value=true and the field is a reference.
        Our Pydantic schema expects plain strings for those fields.
        """
        flattened: Dict[str, Any] = {}
        for k, v in record.items():
            if isinstance(v, dict):
                # If it looks like a reference object
                disp = v.get('display_value') or v.get('displayValue')
                if disp is not None:
                    flattened[k] = disp
                    continue
            flattened[k] = v
        return flattened

# Dependency for FastAPI
_client_instance: ServiceNowClient | None = None
async def get_client() -> ServiceNowClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = ServiceNowClient()
    return _client_instance
