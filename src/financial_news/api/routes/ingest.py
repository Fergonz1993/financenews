"""Ingestion management routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from financial_news.api.dependencies import (
    get_continuous_runner,
    get_ingester,
    get_logger,
    get_settings,
    require_admin_access,
)
from financial_news.api.helpers import (
    _build_freshness_snapshot,
    _ingest_telemetry_with_freshness,
    _normalize_filter_list,
    _parse_csv_filters,
    _parse_csv_source_ids,
    _parse_csv_source_urls,
    _request_id_from_request,
    _with_request_id,
)
from financial_news.api.ingest_state import (
    _get_existing_run_for_idempotency,
    _remember_ingest_idempotency,
)
from financial_news.api.schemas import ConnectorToggleRequest, IngestTriggerRequest

router = APIRouter()

async def _queue_ingest_trigger(
    *,
    request_id: str,
    admin_actor: str,
    source_filter_values: list[str] | None,
    source_url_overrides: list[tuple[str, str]] | None,
    source_ids: list[int] | None,
    idempotency_key: str | None,
    ingester: Any,
    logger: Any,
) -> dict[str, Any]:
    if idempotency_key:
        existing_run_id = _get_existing_run_for_idempotency(idempotency_key)
        if existing_run_id:
            return _with_request_id(
                {
                    "status": "queued",
                    "run_id": existing_run_id,
                    "started_at": datetime.now(UTC).isoformat(),
                    "source_filters": source_filter_values,
                    "source_ids": source_ids,
                    "idempotent_replay": True,
                },
                request_id=request_id,
            )

    logger.info(
        "admin_ingest_trigger request_id=%s actor=%s source_filters=%s source_ids=%s source_override_count=%d idempotency_key=%s",
        request_id,
        admin_actor,
        source_filter_values,
        source_ids,
        len(source_url_overrides or []),
        bool(idempotency_key),
    )
    run_id = await ingester.start_async_ingest(
        source_filters=source_filter_values,
        sources=source_url_overrides,
        source_ids=source_ids,
    )
    _remember_ingest_idempotency(idempotency_key, run_id)
    return _with_request_id(
        {
            "status": "queued",
            "run_id": run_id,
            "started_at": datetime.now(UTC).isoformat(),
            "source_filters": source_filter_values,
            "source_ids": source_ids,
            "idempotent_replay": False,
        },
        request_id=request_id,
    )


@router.post("/api/ingest")
async def run_ingest_sync(
    request: Request,
    source_urls: str | None = Query(None),
    admin_actor: str = Depends(require_admin_access("admin", "ops")),
    ingester: Any = Depends(get_ingester),
    logger: Any = Depends(get_logger),
) -> dict[str, Any]:
    request_id = _request_id_from_request(request)
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
        logger.info(
            "admin_ingest_sync request_id=%s actor=%s source_override_count=%d",
            request_id,
            admin_actor,
            len(sources or []),
        )
        result = await ingester.run_ingest(sources=sources)
        return _with_request_id(result.as_dict(), request_id=request_id)
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
    ingester: Any = Depends(get_ingester),
    logger: Any = Depends(get_logger),
) -> dict[str, Any]:
    request_id = _request_id_from_request(request)
    payload = payload or IngestTriggerRequest()
    idempotency_key = (
        payload.idempotency_key
        or idempotency_key_query
        or request.headers.get("idempotency-key")
        or request.headers.get("x-idempotency-key")
    )
    source_filter_values = _normalize_filter_list(payload.source_filters)
    if source_filter_values is None:
        source_filter_values = _parse_csv_filters(source_filters)

    source_url_overrides = None
    payload_source_urls = _normalize_filter_list(payload.source_urls)
    if payload_source_urls is not None:
        source_url_overrides = [
            (urlparse(url).netloc or f"Source {idx}", url)
            for idx, url in enumerate(payload_source_urls, start=1)
            if str(url).strip()
        ]
    if source_url_overrides is None:
        source_url_overrides = _parse_csv_source_urls(source_urls)

    source_id_values = _parse_csv_source_ids(
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
            ingester=ingester,
            logger=logger,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/api/admin/ingest/run", status_code=202)
async def run_admin_ingest(
    payload: IngestTriggerRequest,
    request: Request,
    admin_actor: str = Depends(require_admin_access("admin", "ops")),
    ingester: Any = Depends(get_ingester),
    logger: Any = Depends(get_logger),
) -> dict[str, Any]:
    request_id = _request_id_from_request(request)
    idempotency_key = (
        payload.idempotency_key
        or request.headers.get("idempotency-key")
        or request.headers.get("x-idempotency-key")
    )
    source_filter_values = _normalize_filter_list(payload.source_filters)
    source_url_overrides = None
    payload_source_urls = _normalize_filter_list(payload.source_urls)
    if payload_source_urls is not None:
        source_url_overrides = [
            (urlparse(url).netloc or f"Source {idx}", url)
            for idx, url in enumerate(payload_source_urls, start=1)
            if str(url).strip()
        ]
    source_id_values = _parse_csv_source_ids(payload.source_ids)
    try:
        return await _queue_ingest_trigger(
            request_id=request_id,
            admin_actor=admin_actor,
            source_filter_values=source_filter_values,
            source_url_overrides=source_url_overrides,
            source_ids=source_id_values,
            idempotency_key=idempotency_key,
            ingester=ingester,
            logger=logger,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/api/ingest/status")
async def get_ingest_status(
    ingester: Any = Depends(get_ingester),
    continuous_runner: Any = Depends(get_continuous_runner),
    logger: Any = Depends(get_logger),
    settings: Any = Depends(get_settings),
) -> dict[str, Any]:
    payload = cast(dict[str, Any], (await ingester.get_last_run()).as_dict())
    try:
        payload["stored_article_count"] = await ingester.count_articles()
    except Exception as exc:
        logger.warning(
            "DB read failed in get_ingest_status; using 0 stored_article_count: %s",
            exc,
        )
        payload["stored_article_count"] = 0
    runner_status = cast(dict[str, Any], continuous_runner.get_status())
    freshness = await _build_freshness_snapshot(
        ingester=ingester,
        runner_status=runner_status,
    )
    payload["scheduled_refresh_seconds"] = max(
        0,
        int(settings.ingest.auto_ingest_interval_seconds),
    )
    payload["continuous_runner"] = runner_status
    payload.update(freshness)
    return payload


@router.get("/api/ingest/telemetry")
async def get_ingest_telemetry(
    ingester: Any = Depends(get_ingester),
    continuous_runner: Any = Depends(get_continuous_runner),
    logger: Any = Depends(get_logger),
    settings: Any = Depends(get_settings),
) -> dict[str, Any]:
    status_payload = await get_ingest_status(
        ingester=ingester,
        continuous_runner=continuous_runner,
        logger=logger,
        settings=settings,
    )
    try:
        source_health = cast(list[dict[str, Any]], await ingester.get_source_health())
    except Exception as exc:
        logger.warning(
            "DB read failed in get_ingest_telemetry; returning empty health: %s",
            exc,
        )
        source_health = []
    freshness = await _build_freshness_snapshot(
        ingester=ingester,
        runner_status=cast(dict[str, Any], continuous_runner.get_status()),
        source_health=source_health,
    )

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "window_minutes": 120,
        "runs": {
            "latest": status_payload,
            "success_rate": _ingest_telemetry_with_freshness(
                status_payload=status_payload,
                source_health=source_health,
                freshness=freshness,
            )["success_rate"],
        },
        "sources": {
            "total": len(source_health),
            "degraded": _ingest_telemetry_with_freshness(
                status_payload=status_payload,
                source_health=source_health,
                freshness=freshness,
            )["degraded_sources"],
            "stale": _ingest_telemetry_with_freshness(
                status_payload=status_payload,
                source_health=source_health,
                freshness=freshness,
            )["stale_sources"],
        },
        "health": source_health,
        "freshness": freshness,
    }


@router.post("/api/ingest/continuous/trigger", status_code=200)
async def trigger_continuous_ingest(
    request: Request,
    admin_actor: str = Depends(require_admin_access("admin", "ops")),
    continuous_runner: Any = Depends(get_continuous_runner),
    logger: Any = Depends(get_logger),
) -> dict[str, Any]:
    try:
        request_id = _request_id_from_request(request)
        logger.info(
            "admin_trigger_continuous_ingest request_id=%s actor=%s",
            request_id,
            admin_actor,
        )
        result = await continuous_runner.trigger_immediate()
        return _with_request_id(
            {"status": "completed", "result": result},
            request_id=request_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Continuous ingest failed: {exc}",
        ) from exc


@router.get("/api/ingest/continuous/status")
async def get_continuous_ingest_status(
    continuous_runner: Any = Depends(get_continuous_runner),
) -> dict[str, Any]:
    return cast(dict[str, Any], continuous_runner.get_status())


@router.post("/api/ingest/continuous/connectors/{connector_name}")
async def set_continuous_connector_state(
    connector_name: str,
    payload: ConnectorToggleRequest,
    request: Request,
    admin_actor: str = Depends(require_admin_access("admin", "ops")),
    continuous_runner: Any = Depends(get_continuous_runner),
    logger: Any = Depends(get_logger),
) -> dict[str, Any]:
    request_id = _request_id_from_request(request)
    try:
        if payload.reset_override:
            result = continuous_runner.clear_connector_override(connector_name)
        elif payload.enabled is None:
            raise HTTPException(
                status_code=400,
                detail="Either enabled must be set or reset_override must be true.",
            )
        else:
            result = continuous_runner.set_connector_enabled(
                connector_name,
                payload.enabled,
            )
        logger.info(
            "admin_connector_toggle request_id=%s actor=%s connector=%s payload=%s",
            request_id,
            admin_actor,
            connector_name,
            result,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _with_request_id(
        {
            "status": "ok",
            "toggle": result,
            "connectors": continuous_runner.get_status().get("connectors", {}),
        },
        request_id=request_id,
    )


@router.get("/api/ingest/runs/{run_id}")
async def get_ingest_run(
    run_id: str,
    ingester: Any = Depends(get_ingester),
) -> dict[str, Any]:
    run = await ingester.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return cast(dict[str, Any], run.as_dict())


@router.get("/api/ingestion/health")
async def get_ingestion_health(
    ingester: Any = Depends(get_ingester),
    logger: Any = Depends(get_logger),
) -> list[dict[str, Any]]:
    try:
        return cast(list[dict[str, Any]], await ingester.get_source_health())
    except Exception as exc:
        logger.warning(
            "DB read failed in get_ingestion_health; returning empty list: %s",
            exc,
        )
        return []
