from __future__ import annotations

from typing import Any

import requests
from requests import HTTPError


class NovaCoreClient:
    def __init__(self, base_url: str, auth_token: str, timeout_seconds: float = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout_seconds = timeout_seconds

    def get(self, endpoint: str) -> Any:
        return self._request_json("GET", endpoint, None)

    def post(self, endpoint: str, payload: dict[str, Any]) -> Any:
        return self._request_json("POST", endpoint, payload)

    def _request_json(
        self,
        method: str,
        endpoint: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        response = requests.request(
            method=method,
            url=f"{self.base_url}{endpoint}",
            headers=self._headers(),
            json=payload,
            timeout=self.timeout_seconds,
        )
        try:
            response.raise_for_status()
        except HTTPError as error:
            if response.status_code == 401:
                raise RuntimeError(
                    "Unauthorized (401): desktop token does not match core token. "
                    "Launch both from `python/start_nova.py` or set the same "
                    "`NOVA_AUTH_TOKEN` for core and desktop."
                ) from error
            raise
        return response.json()

    def _headers(self) -> dict[str, str]:
        return {"x-nova-token": self.auth_token}
