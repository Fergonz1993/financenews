from __future__ import annotations

from pathlib import Path

import financial_news.api.main as api_main
from financial_news.api.container import get_app_container


def test_app_container_is_attached_to_fastapi_state() -> None:
    container = get_app_container(api_main.app)
    assert container.ingester is api_main.ingester
    assert container.source_repo is api_main.source_repo
    assert container.user_settings_repo is api_main.user_settings_repo
    assert container.user_alerts_repo is api_main.user_alerts_repo
    assert container.continuous_runner is api_main.continuous_runner


def test_route_modules_do_not_import_api_main_runtime_globals() -> None:
    routes_dir = Path("src/financial_news/api/routes")
    route_files = sorted(routes_dir.glob("*.py"))
    assert route_files

    for route_file in route_files:
        contents = route_file.read_text(encoding="utf-8")
        assert "from financial_news.api import main as api_main" not in contents
        assert "def _api(" not in contents
