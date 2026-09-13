import requests


class APIClient:

    def __init__(
        self,
        base_url: str,
        token: str = "",
        timeout: int = 5
    ):
        self.base_url = (
            base_url.rstrip("/")
        )

        self.timeout = timeout

        self.session = requests.Session()

        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
        )

        if token:
            self.session.headers.update(
                {
                    "Authorization": (
                        f"Bearer {token}"
                    )
                }
            )

    def send_count_event(
        self,
        event: dict
    ):
        payload = {
            "event_uuid": event["event_uuid"],
            "branch_id": event["branch_id"],
            "camera_name": event["camera_name"],
            "track_id": event.get("track_id"),
            "event_type": event["event_type"],
            "occurred_at": event["occurred_at"]
        }

        try:
            response = self.session.post(
                f"{self.base_url}/count-events",
                json=payload,
                timeout=self.timeout
            )

        except requests.RequestException as error:
            return {
                "success": False,
                "status_code": None,
                "error": str(error)
            }

        if 200 <= response.status_code < 300:
            return {
                "success": True,
                "status_code": response.status_code,
                "error": None
            }

        # Si el servidor usa event_uuid como clave unica,
        # un 409 significa que el evento ya llego antes.
        if response.status_code == 409:
            return {
                "success": True,
                "status_code": response.status_code,
                "error": None
            }

        try:
            detail = response.json()
        except ValueError:
            detail = response.text

        return {
            "success": False,
            "status_code": response.status_code,
            "error": detail
        }

    def close(self):
        self.session.close()
