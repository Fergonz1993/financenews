#!/usr/bin/env python3
"""Backfill legacy `data/ingested_articles.json` data into PostgreSQL."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select

from financial_news.storage import ArticleRepository, SourceRepository, get_session_factory
from financial_news.storage.db import initialize_schema
from financial_news.storage.models import Article
from financial_news.storage.repositories import IngestionRunRepository, SourceConfig


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return normalized or "source"


def _coerce_string(value: Any) -> str:
    return "" if value is None else str(value)


@dataclass
class BackfillSummary:
    rows_read: int
    rows_inserted: int
    rows_skipped: int
    run_id: str

    @property
    def rows_seen(self) -> int:
        return self.rows_read

    def format_for_terminal(self) -> str:
        return (
            f"run_id={self.run_id} "
            f"rows_read={self.rows_read} "
            f"rows_inserted={self.rows_inserted} "
            f"rows_skipped={self.rows_skipped}"
        )


def _load_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Legacy file must contain a JSON array.")

    normalized: list[dict[str, Any]] = []
    for item in payload:
        if isinstance(item, dict):
            normalized.append(dict(item))
    return normalized


async def _sync_sources(
    source_repo: SourceRepository,
    records: list[dict[str, Any]],
) -> dict[str, int]:
    source_names = {_coerce_string(item.get("source")).strip() or "Unknown" for item in records}
    configs: list[SourceConfig] = []
    for name in sorted(source_names):
        source_key = _slugify(name)
        configs.append(
            SourceConfig(
                source_key=source_key,
                name=name,
                url=f"legacy://{source_key}",
                source_type="rss",
                source_category="legacy",
                connector_type="rss",
                legal_basis="legacy_import",
                provider_domain="legacy.local",
                rate_profile="legacy",
                enabled=True,
                crawl_interval_minutes=30,
                rate_limit_per_minute=60,
            )
        )

    sources = await source_repo.upsert_sources(configs)
    return {source.source_key: source.id for source in sources if source.id is not None}


def _normalize_for_db(article_repo: ArticleRepository, record: dict[str, Any]) -> dict[str, Any] | None:
    return article_repo._normalize_for_db(record)


async def _count_new_records(
    article_repo: ArticleRepository,
    normalized: list[dict[str, Any]],
) -> int:
    if not normalized:
        return 0

    url_hashes = [item["url_hash"] for item in normalized]
    dedupe_keys = [item["dedupe_key"] for item in normalized]
    ids = [item["id"] for item in normalized]

    async with article_repo._session_factory() as session:
        existing: set[str] = set()
        if url_hashes:
            result = await session.execute(select(Article.url_hash).where(Article.url_hash.in_(url_hashes)))
            existing.update(row[0] for row in result.all())
        if dedupe_keys:
            result = await session.execute(select(Article.dedupe_key).where(Article.dedupe_key.in_(dedupe_keys)))
            existing.update(row[0] for row in result.all())
        if ids:
            result = await session.execute(select(Article.id).where(Article.id.in_(ids)))
            existing.update(row[0] for row in result.all())

    inserted = 0
    for item in normalized:
        if item["url_hash"] in existing or item["dedupe_key"] in existing or item["id"] in existing:
            continue
        inserted += 1
    return inserted


async def _backfill(
    records: list[dict[str, Any]],
    run_id: str,
    dry_run: bool,
) -> BackfillSummary:
    session_factory = get_session_factory()
    await initialize_schema()
    source_repo = SourceRepository(session_factory=session_factory)
    source_map = await _sync_sources(source_repo, records)

    article_repo = ArticleRepository(session_factory=session_factory)
    normalized: list[dict[str, Any]] = []
    for item in records:
        source_name = _coerce_string(item.get("source")).strip() or "Unknown"
        item["source_id"] = source_map.get(_slugify(source_name))
        normalized_item = _normalize_for_db(article_repo, item)
        if normalized_item:
            normalized.append(normalized_item)

    if dry_run:
        inserted = await _count_new_records(article_repo, normalized)
        skipped = len(normalized) - inserted
        return BackfillSummary(rows_read=len(normalized), rows_inserted=inserted, rows_skipped=skipped, run_id=run_id)

    run_repo = IngestionRunRepository(session_factory=session_factory)
    await run_repo.create_run(run_id=run_id, requested_sources=max(len(source_map), 1))
    run_result = await article_repo.upsert_deduplicated(run_id=run_id, items=normalized)

    await run_repo.finish_run(
        run_id=run_id,
        items_seen=run_result.items_seen,
        items_stored=run_result.items_stored,
        items_skipped=run_result.items_skipped,
        failed_sources=0,
        source_errors=0,
        error_summary=[],
        source_results=[],
        status="completed",
    )

    return BackfillSummary(
        rows_read=len(normalized),
        rows_inserted=run_result.items_stored,
        rows_skipped=run_result.items_skipped,
        run_id=run_id,
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill ingested_articles.json into PostgreSQL with idempotent inserts."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="data/ingested_articles.json",
        help="Path to the legacy JSON file.",
    )
    parser.add_argument(
        "--run-id",
        default="backfill",
        help="Run identifier to attach to ingestion metadata.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Evaluate dedupe impact without writing rows.",
    )
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    source_path = Path(args.path)
    if not source_path.exists():
        raise FileNotFoundError(f"Legacy source file not found: {source_path}")

    records = _load_records(source_path)
    summary = asyncio.run(_backfill(records=records, run_id=args.run_id, dry_run=args.dry_run))
    print(summary.format_for_terminal())


if __name__ == "__main__":
    main()
