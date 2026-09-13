import requests


class APIClient:

    def __init__(
        self,
        base_url: str,
        token: str = "",
        timeout: int = 5,
        client_id: str = "",
        client_token: str = ""
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client_id = client_id.strip()
        self.client_token = client_token.strip()
        self.legacy_token = token.strip()
        self.managed_client = bool(
            self.client_id and self.client_token
        )

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
        )

        if self.managed_client:
            self.session.headers.update(
                {
                    "Authorization": f"Bearer {self.client_token}",
                    "X-Client-ID": self.client_id
                }
            )
        elif self.legacy_token:
            self.session.headers.update(
                {
                    "Authorization": f"Bearer {self.legacy_token}"
                }
            )

    def _request(
        self,
        method: str,
        path: str,
        payload: dict | None = None
    ):
        try:
            response = self.session.request(
                method=method,
                url=f"{self.base_url}{path}",
                json=payload,
                timeout=self.timeout
            )
        except requests.RequestException as error:
            return {
                "success": False,
                "status_code": None,
                "error": str(error),
                "data": None
            }

        try:
            data = response.json()
        except ValueError:
            data = response.text or None

        if 200 <= response.status_code < 300:
            return {
                "success": True,
                "status_code": response.status_code,
                "error": None,
                "data": data
            }

        # count-events es idempotente por event_uuid.
        if response.status_code == 409 and path == "/count-events":
            return {
                "success": True,
                "status_code": response.status_code,
                "error": None,
                "data": data
            }

        return {
            "success": False,
            "status_code": response.status_code,
            "error": data,
            "data": data
        }

    def send_count_event(self, event: dict):
        payload = {
            "event_uuid": event["event_uuid"],
            "branch_id": event["branch_id"],
            "camera_name": event["camera_name"],
            "track_id": event.get("track_id"),
            "event_type": event["event_type"],
            "occurred_at": event["occurred_at"]
        }
        return self._request(
            "POST",
            "/count-events",
            payload
        )

    def send_heartbeat(
        self,
        branch_id: int,
        camera_name: str,
        app_version: str = "",
        pending_events: int = 0,
        last_error: str | None = None
    ):
        if self.managed_client:
            return self._request(
                "POST",
                "/client/heartbeat",
                {
                    "app_version": app_version or None,
                    "pending_events": max(0, int(pending_events)),
                    "last_error": last_error
                }
            )

        return self._request(
            "POST",
            "/cameras/heartbeat",
            {
                "branch_id": branch_id,
                "camera_name": camera_name
            }
        )

    def get_remote_config(self):
        if not self.managed_client:
            return {
                "success": False,
                "status_code": None,
                "error": "Cliente no administrado",
                "data": None
            }

        return self._request(
            "GET",
            "/client/config"
        )

    def close(self):
        self.session.close()
