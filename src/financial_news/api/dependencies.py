"""FastAPI dependency helpers."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import HTTPException, Request


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
