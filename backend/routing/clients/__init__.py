"""HTTP clients for the external routing and weather services."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class UpstreamError(Exception):
    """An external service failed or returned something unusable (-> HTTP 502)."""

    def __init__(self, service: str, message: str, status: int = 502):
        super().__init__(f"{service}: {message}")
        self.service = service
        self.message = message
        self.status = status


class UpstreamTimeout(UpstreamError):
    def __init__(self, service: str):
        super().__init__(service, "timed out", status=504)


_session = requests.Session()


def http_json(
    service: str,
    method: str,
    url: str,
    *,
    timeout: float,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> Any:
    headers = {"User-Agent": settings.HTTP_USER_AGENT, "Accept": "application/json"}
    try:
        resp = _session.request(
            method, url, params=params, json=body, headers=headers, timeout=timeout
        )
    except requests.Timeout as exc:
        raise UpstreamTimeout(service) from exc
    except requests.RequestException as exc:
        raise UpstreamError(service, "unreachable") from exc
    if resp.status_code >= 400:
        detail = resp.text[:200]
        logger.warning("%s HTTP %s: %s", service, resp.status_code, detail)
        raise UpstreamError(service, f"HTTP {resp.status_code}: {detail}")
    try:
        return resp.json()
    except ValueError as exc:
        raise UpstreamError(service, "invalid JSON") from exc


def cache_key(prefix: str, payload: Any) -> str:
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return f"{prefix}:{digest[:32]}"
