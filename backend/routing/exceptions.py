"""Consistent error envelope: {"error": {"code", "message", "details"?}}."""

from __future__ import annotations

from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .clients import UpstreamError, UpstreamTimeout


def _first_message(detail) -> str:
    if isinstance(detail, list) and detail:
        return _first_message(detail[0])
    if isinstance(detail, dict) and detail:
        key, val = next(iter(detail.items()))
        msg = _first_message(val)
        return msg if key == "non_field_errors" else f"{key}: {msg}"
    return str(detail)


def api_exception_handler(exc, context):
    if isinstance(exc, UpstreamError):
        code = "upstream_timeout" if isinstance(exc, UpstreamTimeout) else "upstream_error"
        if exc.status == 422:
            code = "no_route"
        return Response(
            {"error": {"code": code, "message": f"{exc.service}: {exc.message}"}},
            status=exc.status,
        )

    response = exception_handler(exc, context)
    if response is None:
        return None
    if isinstance(exc, exceptions.ValidationError):
        response.data = {
            "error": {
                "code": "invalid_request",
                "message": _first_message(exc.detail),
                "details": exc.detail,
            }
        }
    else:
        code = getattr(exc, "default_code", "error")
        if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            code = "rate_limited"
        response.data = {"error": {"code": code, "message": _first_message(response.data)}}
    return response
