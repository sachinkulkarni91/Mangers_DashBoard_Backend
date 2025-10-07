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

    # ----------------- search endpoints -----------------
    async def search_users(self, term: str, limit: int = 20, fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Search sys_user table by name or user id.
        If fields is provided (and not ['*']), restrict output to those fields using sysparm_fields.
        If fields is None or contains '*', all available fields will be returned.
        """
        query = f"nameLIKE{term}^ORuser_nameLIKE{term}"
        params: Dict[str, Any] = {
            'sysparm_query': query,
            'sysparm_limit': str(limit),
            'sysparm_display_value': 'true',
        }
        if fields and not (len(fields) == 1 and fields[0] == '*'):
            params['sysparm_fields'] = ','.join(fields)
        try:
            resp = await self._client.get('/table/sys_user', params=params)
            self._handle_redirect(resp, 'search users')
            resp.raise_for_status()
            data = resp.json().get('result', [])
            return [self._normalize_record(r) for r in data]
        except httpx.RequestError as e:
            logger.error(f"ServiceNow connection error search users: {e}")
            raise_gateway_error("Unable to connect to ServiceNow (search users)")
        except httpx.HTTPStatusError as e:
            logger.error(f"ServiceNow HTTP error search users: {e.response.status_code} {e.response.text}")
            raise_gateway_error(f"ServiceNow responded with status {e.response.status_code}")

    async def search_locations(self, term: str, limit: int = 20, fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Search cmn_location table by name.
        If fields is provided (and not ['*']), restrict output to those fields.
        If fields is None or contains '*', return all fields.
        """
        query = f"nameLIKE{term}"
        params: Dict[str, Any] = {
            'sysparm_query': query,
            'sysparm_limit': str(limit),
            'sysparm_display_value': 'true',
        }
        if fields and not (len(fields) == 1 and fields[0] == '*'):
            params['sysparm_fields'] = ','.join(fields)
        try:
            resp = await self._client.get('/table/cmn_location', params=params)
            self._handle_redirect(resp, 'search locations')
            resp.raise_for_status()
            data = resp.json().get('result', [])
            return [self._normalize_record(r) for r in data]
        except httpx.RequestError as e:
            logger.error(f"ServiceNow connection error search locations: {e}")
            raise_gateway_error("Unable to connect to ServiceNow (search locations)")
        except httpx.HTTPStatusError as e:
            logger.error(f"ServiceNow HTTP error search locations: {e.response.status_code} {e.response.text}")
            raise_gateway_error(f"ServiceNow responded with status {e.response.status_code}")

    # ----------------- affected users derivation -----------------
    async def get_incident_affected_users(
        self,
        number: str,
        incident_fields: Optional[List[str]] = None,
        user_fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Derive affected users from standard incident user reference fields and list fields.

        Pattern 1 approach: collects sys_ids from caller_id, opened_by, requested_by, assigned_to, closed_by,
        watch_list, additional_assignee_list and optional custom fields (u_affected_user, u_affected_users).

        If user_fields is provided (and not ['*']), restrict sys_user fetch to those fields.
        Returns normalized user records (display values where references appear).
        """
        # Fields needed from incident to gather user references
        base_incident_fields = [
            'sys_id','caller_id','opened_by','requested_by','assigned_to','closed_by',
            'watch_list','additional_assignee_list','u_affected_user','u_affected_users'
        ]
        if incident_fields:
            # ensure base fields included
            fetch_fields = list({*base_incident_fields, *incident_fields})
        else:
            fetch_fields = base_incident_fields

        params = {
            'sysparm_query': f'number={number}',
            'sysparm_limit': '1',
            'sysparm_fields': ','.join(fetch_fields),
            'sysparm_display_value': 'false'  # need raw sys_ids
        }
        try:
            resp = await self._client.get('/table/incident', params=params)
            self._handle_redirect(resp, f'get incident affected users {number}')
            resp.raise_for_status()
        except httpx.RequestError as e:
            logger.error(f"ServiceNow connection error get incident affected users {number}: {e}")
            raise_gateway_error("Unable to connect to ServiceNow (affected users - incident fetch)")
        except httpx.HTTPStatusError as e:
            logger.error(f"ServiceNow HTTP error get incident affected users {number}: {e.response.status_code} {e.response.text}")
            raise_gateway_error(f"ServiceNow responded with status {e.response.status_code}")

        inc_list = resp.json().get('result', [])
        if not inc_list:
            return []
        incident = inc_list[0]

        user_ids: set[str] = set()

        def add_value(val: Any):
            if not val:
                return
            if isinstance(val, dict):
                vid = val.get('value')
                if vid:
                    user_ids.add(vid)
            elif isinstance(val, str):
                if ',' in val:
                    for part in val.split(','):
                        p = part.strip()
                        if p:
                            user_ids.add(p)
                else:
                    # heuristic: sys_ids are 32 char hex normally
                    if len(val) >= 32:
                        user_ids.add(val)

        scan_fields = [
            'caller_id','opened_by','requested_by','assigned_to','closed_by',
            'watch_list','additional_assignee_list','u_affected_user','u_affected_users'
        ]
        for f in scan_fields:
            add_value(incident.get(f))

        if not user_ids:
            return []

        user_params: Dict[str, Any] = {
            'sysparm_query': 'sys_idIN' + ','.join(sorted(user_ids)),
            'sysparm_display_value': 'true'
        }
        if user_fields and not (len(user_fields) == 1 and user_fields[0] == '*'):
            user_params['sysparm_fields'] = ','.join(user_fields)

        try:
            u_resp = await self._client.get('/table/sys_user', params=user_params)
            self._handle_redirect(u_resp, f'get affected users list {number}')
            u_resp.raise_for_status()
            data = u_resp.json().get('result', [])
            return [self._normalize_record(u) for u in data]
        except httpx.RequestError as e:
            logger.error(f"ServiceNow connection error affected users list {number}: {e}")
            raise_gateway_error("Unable to connect to ServiceNow (affected users - user fetch)")
        except httpx.HTTPStatusError as e:
            logger.error(f"ServiceNow HTTP error affected users list {number}: {e.response.status_code} {e.response.text}")
            raise_gateway_error(f"ServiceNow responded with status {e.response.status_code}")

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

    # ----------------- affected users (pattern 1) -----------------
    async def get_incident_affected_users(
        self,
        number: str,
        include_fields: Optional[List[str]] = None,
        user_fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Derive affected users from standard incident user-related fields plus watch/assignee lists.

        Steps:
        1. Fetch the incident (display_value=false to retain sys_ids for reference + list fields)
        2. Collect sys_ids from predefined fields (single reference or comma-separated multi lists)
        3. Query sys_user for those sys_ids (optionally restricted by user_fields)

        If user_fields is None or ['*'] -> no sysparm_fields filter (all fields returned by instance defaults).
        """
        incident_field_candidates = include_fields or [
            'sys_id',
            'caller_id',
            'opened_by',
            'requested_by',
            'assigned_to',
            'watch_list',
            'additional_assignee_list',
            'closed_by',
            # custom potential fields
            'u_affected_user',
            'u_affected_users',
        ]
        params = {
            'sysparm_query': f'number={number}',
            'sysparm_limit': '1',
            'sysparm_fields': ','.join(incident_field_candidates),
            'sysparm_display_value': 'false'
        }
        try:
            resp = await self._client.get('/table/incident', params=params)
            self._handle_redirect(resp, f'get incident (affected users) {number}')
            resp.raise_for_status()
        except httpx.RequestError:
            raise_gateway_error('Unable to connect to ServiceNow (affected users - incident fetch)')
        except httpx.HTTPStatusError as e:
            raise_gateway_error(f'ServiceNow responded with status {e.response.status_code}')

        results = resp.json().get('result', [])
        if not results:
            return []
        incident = results[0]

        user_ids: set[str] = set()

        def _maybe_add(value: Any):
            if not value:
                return
            if isinstance(value, str):
                # Could be a single sys_id or comma-separated list (watch_list like value1,value2,...)
                if ',' in value:
                    for part in value.split(','):
                        part = part.strip()
                        if part:
                            user_ids.add(part)
                else:
                    # Heuristic: sys_ids are 32 chars; don't strictly rely on length though
                    if len(value) >= 32:
                        user_ids.add(value)
            elif isinstance(value, dict):
                # reference structure: {"link": "...", "value": "sys_id"}
                val = value.get('value')
                if val:
                    user_ids.add(val)

        fields_to_scan = [
            'caller_id', 'opened_by', 'requested_by', 'assigned_to', 'closed_by',
            'watch_list', 'additional_assignee_list', 'u_affected_user', 'u_affected_users'
        ]
        for f in fields_to_scan:
            _maybe_add(incident.get(f))

        if not user_ids:
            return []

        user_params: Dict[str, Any] = {
            'sysparm_query': 'sys_idIN' + ','.join(sorted(user_ids)),
            'sysparm_display_value': 'true'
        }
        if user_fields and not (len(user_fields) == 1 and user_fields[0] == '*'):
            user_params['sysparm_fields'] = ','.join(user_fields)

        try:
            u_resp = await self._client.get('/table/sys_user', params=user_params)
            self._handle_redirect(u_resp, f'get affected users for {number}')
            u_resp.raise_for_status()
            user_data = u_resp.json().get('result', [])
            return [self._normalize_record(u) for u in user_data]
        except httpx.RequestError:
            raise_gateway_error('Unable to connect to ServiceNow (affected users - user fetch)')
        except httpx.HTTPStatusError as e:
            raise_gateway_error(f'ServiceNow responded with status {e.response.status_code}')

# Dependency for FastAPI
_client_instance: ServiceNowClient | None = None
async def get_client() -> ServiceNowClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = ServiceNowClient()
    return _client_instance
