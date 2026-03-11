"""FastAPI dependency helpers."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import HTTPException, Request

from financial_news.api.container import AppContainer, get_request_container


def get_container(request: Request) -> AppContainer:
    """Resolve the shared app container from request state."""
    return get_request_container(request)


def get_settings(request: Request) -> object:
    return get_container(request).settings


def get_logger(request: Request) -> object:
    return get_container(request).logger


def get_ingester(request: Request) -> object:
    return get_container(request).ingester


def get_source_repo(request: Request) -> object:
    return get_container(request).source_repo


def get_user_settings_repo(request: Request) -> object:
    return get_container(request).user_settings_repo


def get_user_alerts_repo(request: Request) -> object:
    return get_container(request).user_alerts_repo


def get_continuous_runner(request: Request) -> object:
    return get_container(request).continuous_runner


def get_notification_manager(request: Request) -> object:
    return get_container(request).notification_manager


async def initialize_schema_if_needed() -> None:
    """Invoke schema initialization through the compatibility module."""
    from financial_news.api import main as api_main

    await api_main.initialize_schema()


def require_admin_access(*roles: str) -> Callable[[Request], str]:
    """Resolve admin access dynamically through the compatibility module."""

    required_roles = {role.strip().lower() for role in roles if role and role.strip()}

    def _dependency(request: Request) -> str:
        from financial_news.api import main as api_main

        actor = api_main._require_admin_access(request)
        if not api_main.ADMIN_API_KEY or not required_roles:
            return actor
        role = request.headers.get("x-admin-role", "admin").strip().lower()
        if role not in required_roles:
            raise HTTPException(
                status_code=403,
                detail="Role not permitted for this endpoint",
            )
        return actor

    return _dependency
