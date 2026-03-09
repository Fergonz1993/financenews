"""Ingestion management routes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from financial_news.api.dependencies import require_admin_access
from financial_news.api.schemas import ConnectorToggleRequest, IngestTriggerRequest

router = APIRouter()


def _api() -> Any:
    from financial_news.api import main as api_main

    return api_main


async def _queue_ingest_trigger(
    *,
    request_id: str,
    admin_actor: str,
    source_filter_values: list[str] | None,
    source_url_overrides: list[tuple[str, str]] | None,
    source_ids: list[int] | None,
    idempotency_key: str | None,
) -> dict[str, Any]:
    api_main = _api()
    if idempotency_key:
        existing_run_id = api_main._get_existing_run_for_idempotency(idempotency_key)
        if existing_run_id:
            return cast(
                dict[str, Any],
                api_main._with_request_id(
                    {
                        "status": "queued",
                        "run_id": existing_run_id,
                        "started_at": datetime.now(UTC).isoformat(),
                        "source_filters": source_filter_values,
                        "source_ids": source_ids,
                        "idempotent_replay": True,
                    },
                    request_id=request_id,
                ),
            )

    api_main.logger.info(
        "admin_ingest_trigger request_id=%s actor=%s source_filters=%s source_ids=%s source_override_count=%d idempotency_key=%s",
        request_id,
        admin_actor,
        source_filter_values,
        source_ids,
        len(source_url_overrides or []),
        bool(idempotency_key),
    )
    run_id = await api_main.ingester.start_async_ingest(
        source_filters=source_filter_values,
        sources=source_url_overrides,
        source_ids=source_ids,
    )
    api_main._remember_ingest_idempotency(idempotency_key, run_id)
    return cast(
        dict[str, Any],
        api_main._with_request_id(
        {
            "status": "queued",
            "run_id": run_id,
            "started_at": datetime.now(UTC).isoformat(),
            "source_filters": source_filter_values,
            "source_ids": source_ids,
            "idempotent_replay": False,
        },
            request_id=request_id,
        ),
    )


@router.post("/api/ingest")
async def run_ingest_sync(
    request: Request,
    source_urls: str | None = Query(None),
    admin_actor: str = Depends(require_admin_access("admin", "ops")),
) -> dict[str, Any]:
    api_main = _api()
    request_id = api_main._request_id_from_request(request)
    sources: list[tuple[str, str]] | None = None
    if source_urls:
        override_sources = [url.strip() for url in source_urls.split(",") if url.strip()]
        if not override_sources:
            raise HTTPException(status_code=400, detail="source_urls cannot be empty")
        sources = [
            (urlparse(url).netloc or f"Source {idx}", url)
            for idx, url in enumerate(override_sources, start=1)
        ]

    try:
        api_main.logger.info(
            "admin_ingest_sync request_id=%s actor=%s source_override_count=%d",
            request_id,
            admin_actor,
            len(sources or []),
        )
        result = await api_main.ingester.run_ingest(sources=sources)
        return cast(
            dict[str, Any],
            api_main._with_request_id(result.as_dict(), request_id=request_id),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {exc}") from exc


@router.post("/api/ingest/trigger", status_code=202)
async def run_ingest_trigger(
    request: Request,
    payload: IngestTriggerRequest | None = None,
    source_filters: str | None = Query(None),
    source_urls: str | None = Query(None),
    source_ids: str | None = Query(None),
    idempotency_key_query: str | None = Query(None),
    admin_actor: str = Depends(require_admin_access("admin", "ops")),
) -> dict[str, Any]:
    api_main = _api()
    request_id = api_main._request_id_from_request(request)
    payload = payload or IngestTriggerRequest()
    idempotency_key = (
        payload.idempotency_key
        or idempotency_key_query
        or request.headers.get("idempotency-key")
        or request.headers.get("x-idempotency-key")
    )
    source_filter_values = api_main._normalize_filter_list(payload.source_filters)
    if source_filter_values is None:
        source_filter_values = api_main._parse_csv_filters(source_filters)

    source_url_overrides = None
    payload_source_urls = api_main._normalize_filter_list(payload.source_urls)
    if payload_source_urls is not None:
        source_url_overrides = [
            (urlparse(url).netloc or f"Source {idx}", url)
            for idx, url in enumerate(payload_source_urls, start=1)
            if str(url).strip()
        ]
    if source_url_overrides is None:
        source_url_overrides = api_main._parse_csv_source_urls(source_urls)

    source_id_values = api_main._parse_csv_source_ids(
        payload.source_ids if payload.source_ids is not None else source_ids
    )
    if source_url_overrides is not None and not source_url_overrides:
        raise HTTPException(status_code=400, detail="source_urls cannot be empty")

    try:
        return await _queue_ingest_trigger(
            request_id=request_id,
            admin_actor=admin_actor,
            source_filter_values=source_filter_values,
            source_url_overrides=source_url_overrides,
            source_ids=source_id_values,
            idempotency_key=idempotency_key,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/api/admin/ingest/run", status_code=202)
async def run_admin_ingest(
    payload: IngestTriggerRequest,
    request: Request,
    admin_actor: str = Depends(require_admin_access("admin", "ops")),
) -> dict[str, Any]:
    api_main = _api()
    request_id = api_main._request_id_from_request(request)
    idempotency_key = (
        payload.idempotency_key
        or request.headers.get("idempotency-key")
        or request.headers.get("x-idempotency-key")
    )
    source_filter_values = api_main._normalize_filter_list(payload.source_filters)
    source_url_overrides = None
    payload_source_urls = api_main._normalize_filter_list(payload.source_urls)
    if payload_source_urls is not None:
        source_url_overrides = [
            (urlparse(url).netloc or f"Source {idx}", url)
            for idx, url in enumerate(payload_source_urls, start=1)
            if str(url).strip()
        ]
    source_id_values = api_main._parse_csv_source_ids(payload.source_ids)
    try:
        return await _queue_ingest_trigger(
            request_id=request_id,
            admin_actor=admin_actor,
            source_filter_values=source_filter_values,
            source_url_overrides=source_url_overrides,
            source_ids=source_id_values,
            idempotency_key=idempotency_key,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/api/ingest/status")
async def get_ingest_status() -> dict[str, Any]:
    api_main = _api()
    payload = (await api_main.ingester.get_last_run()).as_dict()
    try:
        payload["stored_article_count"] = await api_main.ingester.count_articles()
    except Exception as exc:
        api_main.logger.warning(
            "DB read failed in get_ingest_status; using 0 stored_article_count: %s",
            exc,
        )
        payload["stored_article_count"] = 0
    payload["scheduled_refresh_seconds"] = api_main.AUTO_INGEST_INTERVAL_SECONDS
    payload["continuous_runner"] = api_main.continuous_runner.get_status()
    return cast(dict[str, Any], payload)


@router.get("/api/ingest/telemetry")
async def get_ingest_telemetry() -> dict[str, Any]:
    api_main = _api()
    status_payload = await get_ingest_status()
    try:
        source_health = await api_main.ingester.get_source_health()
    except Exception as exc:
        api_main.logger.warning(
            "DB read failed in get_ingest_telemetry; returning empty health: %s",
            exc,
        )
        source_health = []

    requested_sources = int(status_payload.get("requested_sources") or 0)
    failed_sources = int(status_payload.get("failed_sources") or 0)
    success_rate = None
    if requested_sources > 0:
        success_rate = max(
            0.0,
            (requested_sources - failed_sources) / requested_sources,
        )

    stale_cutoff = datetime.now(UTC) - timedelta(minutes=120)
    stale_sources = 0
    degraded_sources = 0
    for health_row in source_health:
        last_success_at = health_row.get("last_success_at")
        parsed_last_success_at: datetime | None = None
        if isinstance(last_success_at, str) and last_success_at.strip():
            try:
                parsed_last_success_at = datetime.fromisoformat(
                    last_success_at.replace("Z", "+00:00")
                )
                if parsed_last_success_at.tzinfo is None:
                    parsed_last_success_at = parsed_last_success_at.replace(tzinfo=UTC)
            except ValueError:
                parsed_last_success_at = None

        if parsed_last_success_at is None or parsed_last_success_at < stale_cutoff:
            stale_sources += 1
        if (
            bool(health_row.get("disabled_by_failure"))
            or int(health_row.get("consecutive_failures") or 0) > 0
            or bool(health_row.get("last_error"))
        ):
            degraded_sources += 1

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "window_minutes": 120,
        "runs": {
            "latest": status_payload,
            "success_rate": success_rate,
        },
        "sources": {
            "total": len(source_health),
            "degraded": degraded_sources,
            "stale": stale_sources,
        },
        "health": source_health,
    }


@router.post("/api/ingest/continuous/trigger", status_code=200)
async def trigger_continuous_ingest(
    request: Request,
    admin_actor: str = Depends(require_admin_access("admin", "ops")),
) -> dict[str, Any]:
    api_main = _api()
    try:
        request_id = api_main._request_id_from_request(request)
        api_main.logger.info(
            "admin_trigger_continuous_ingest request_id=%s actor=%s",
            request_id,
            admin_actor,
        )
        result = await api_main.continuous_runner.trigger_immediate()
        return cast(
            dict[str, Any],
            api_main._with_request_id(
            {"status": "completed", "result": result},
            request_id=request_id,
            ),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Continuous ingest failed: {exc}",
        ) from exc


@router.get("/api/ingest/continuous/status")
async def get_continuous_ingest_status() -> dict[str, Any]:
    api_main = _api()
    return cast(dict[str, Any], api_main.continuous_runner.get_status())


@router.post("/api/ingest/continuous/connectors/{connector_name}")
async def set_continuous_connector_state(
    connector_name: str,
    payload: ConnectorToggleRequest,
    request: Request,
    admin_actor: str = Depends(require_admin_access("admin", "ops")),
) -> dict[str, Any]:
    api_main = _api()
    request_id = api_main._request_id_from_request(request)
    try:
        if payload.reset_override:
            result = api_main.continuous_runner.clear_connector_override(connector_name)
        elif payload.enabled is None:
            raise HTTPException(
                status_code=400,
                detail="Either enabled must be set or reset_override must be true.",
            )
        else:
            result = api_main.continuous_runner.set_connector_enabled(
                connector_name,
                payload.enabled,
            )
        api_main.logger.info(
            "admin_connector_toggle request_id=%s actor=%s connector=%s payload=%s",
            request_id,
            admin_actor,
            connector_name,
            result,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return cast(
        dict[str, Any],
        api_main._with_request_id(
        {
            "status": "ok",
            "toggle": result,
            "connectors": api_main.continuous_runner.get_status().get("connectors", {}),
        },
            request_id=request_id,
        ),
    )


@router.get("/api/ingest/runs/{run_id}")
async def get_ingest_run(run_id: str) -> dict[str, Any]:
    api_main = _api()
    run = await api_main.ingester.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return cast(dict[str, Any], run.as_dict())


@router.get("/api/ingestion/health")
async def get_ingestion_health() -> list[dict[str, Any]]:
    api_main = _api()
    try:
        return cast(list[dict[str, Any]], await api_main.ingester.get_source_health())
    except Exception as exc:
        api_main.logger.warning(
            "DB read failed in get_ingestion_health; returning empty list: %s",
            exc,
        )
        return []
