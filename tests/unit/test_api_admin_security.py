"""Unit tests for admin auth and request-id middleware."""

from __future__ import annotations

import pytest
from starlette.requests import Request
from starlette.responses import Response

from financial_news.api import main as api_main


def _build_request(headers: dict[str, str] | None = None) -> Request:
    headers = headers or {}
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/ingest/trigger",
        "headers": raw_headers,
    }
    return Request(scope)


def test_require_admin_access_backward_compatible_when_key_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "ADMIN_API_KEY", "")
    request = _build_request()
    actor = api_main._require_admin_access(request)
    assert actor == "anonymous"


def test_require_admin_access_rejects_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "ADMIN_API_KEY", "secret-key")
    request = _build_request()
    with pytest.raises(api_main.HTTPException) as exc_info:
        api_main._require_admin_access(request)
    assert exc_info.value.status_code == 401


def test_require_admin_access_rejects_wrong_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "ADMIN_API_KEY", "secret-key")
    monkeypatch.setattr(api_main, "ADMIN_ALLOWED_ROLES", {"admin"})
    request = _build_request(
        {
            "x-admin-api-key": "secret-key",
            "x-admin-role": "viewer",
            "x-admin-user": "fern",
        }
    )
    with pytest.raises(api_main.HTTPException) as exc_info:
        api_main._require_admin_access(request)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_request_id_middleware_sets_response_header() -> None:
    request = _build_request({"x-request-id": "req-123"})

    async def _call_next(req: Request) -> Response:
        assert req.state.request_id == "req-123"
        return Response("ok", status_code=200)

    response = await api_main.request_id_middleware(request, _call_next)
    assert response.headers["X-Request-Id"] == "req-123"
