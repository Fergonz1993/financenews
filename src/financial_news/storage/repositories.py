"""Repository layer for PostgreSQL-backed ingestion and article persistence."""

from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, delete, func, or_, select

from financial_news.storage.models import (
    Article,
    ArticleDedupe,
    IngestionRun,
    IngestionState,
    Source,
    UserSavedArticle,
    UserSettings,
    UserAlertPreferences,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def _slugify(value: Any) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())
    return normalized.strip("-")


def _coerce_list(value: Any, *, max_items: int = 20) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item][:max_items]
    return [str(value)]


def _normalize_title_value(value: Any) -> str:
    text = str(value or "").strip()
    return " ".join(text.split())


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not value:
        return datetime.now(UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return datetime.now(UTC)
    return datetime.now(UTC)


def _canonicalize_url(value: str) -> str:
    normalized = (value or "").strip().lower()
    if not normalized:
        return ""
    if "://" not in normalized:
        return normalized

    if "#" in normalized:
        normalized = normalized.split("#", 1)[0]
    for prefix in ("utm_source=", "utm_medium=", "utm_campaign=", "utm_term="):
        if prefix in normalized:
            base, _sep, tail = normalized.partition("?")
            if tail:
                params = [p for p in tail.split("&") if not p.lower().startswith(prefix)]
                normalized = base if not params else base + "?" + "&".join(params)
            break

    return normalized.rstrip("/")


def _hash_value(value: str) -> str:
    normalized = (value or "").strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _coerce_opt_str(value: Any) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


def _normalize_search_text(value: Any) -> str:
    if not value:
        return ""
    normalized = str(value).lower()
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


def _collect_aliases(search: str) -> list[str]:
    aliases = [search]
    if search in {"finance", "financial"}:
        aliases.extend(["finance", "financial", "market", "stocks"])
    if search in {"capital markets", "capital market"}:
        aliases.extend(
            [
                "capital markets",
                "capital market",
                "equity market",
                "bond market",
            ]
        )
    if search in {"ai", "artificial intelligence"}:
        aliases.extend(
            [
                "artificial intelligence",
                "ai",
                "machine learning",
                "large language model",
            ]
        )
    return aliases


def _search_match(article: dict[str, Any], aliases: list[str]) -> bool:
    haystack = " ".join(
        [
            _normalize_search_text(article.get("title")),
            _normalize_search_text(article.get("content")),
            _normalize_search_text(article.get("summarized_headline")),
            _normalize_search_text(article.get("source")),
            _normalize_search_text(article.get("topics", [])),
            _normalize_search_text(article.get("key_entities", [])),
        ]
    )
    haystack = f" {haystack} "
    for alias in aliases:
        if " " in alias:
            alias_norm = f" {alias} "
            if alias_norm in haystack:
                return True
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", haystack):
            return True
    return False


def _topic_matches(article: dict[str, Any], topic_slug: str) -> bool:
    return any(_slugify(item) == topic_slug for item in article.get("topics", []))


def _extract_single_column(rows: Iterable[Any], idx: int) -> set[str]:
    return {str(row[idx]) for row in rows if row[idx] is not None}


@dataclass(slots=True)
class SourceConfig:
    source_key: str
    name: str
    url: str
    source_type: str = "rss"
    enabled: bool | None = None
    crawl_interval_minutes: int = 30
    rate_limit_per_minute: int = 60
    source_category: str | None = None
    connector_type: str | None = None
    terms_url: str | None = None
    legal_basis: str | None = None
    provider_domain: str | None = None
    rate_profile: str | None = None
    requires_api_key: bool = False
    requires_user_agent: bool = False
    user_agent: str | None = None
    retry_policy: dict[str, Any] | None = None
    parser_contract: dict[str, Any] | None = None


@dataclass(slots=True)
class IngestResult:
    requested_sources: int = 0
    items_seen: int = 0
    items_stored: int = 0
    items_skipped: int = 0
    failed_sources: int = 0
    errors: list[str] | None = None
    run_id: str | None = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


class SourceRepository:
    """Source registry persistence."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_id(self, source_id: int) -> Source | None:
        async with self._session_factory() as session:
            result = await session.execute(select(Source).where(Source.id == source_id))
            return result.scalar_one_or_none()

    async def get_by_identifier(self, identifier: int | str) -> Source | None:
        if isinstance(identifier, int):
            return await self.get_by_id(identifier)

        identifier_text = str(identifier).strip()
        if not identifier_text:
            return None
        if identifier_text.isdigit():
            found_by_id = await self.get_by_id(int(identifier_text))
            if found_by_id is not None:
                return found_by_id
        return await self.get_by_key(identifier_text)

    async def get_by_key(self, source_key: str) -> Source | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(Source).where(Source.source_key == source_key)
            )
            return result.scalar_one_or_none()

    async def list_sources(
        self,
        *,
        enabled_only: bool = False,
        source_category: str | None = None,
        connector_type: str | None = None,
    ) -> list[Source]:
        async with self._session_factory() as session:
            stmt = select(Source).order_by(Source.source_key.asc())
            if enabled_only:
                stmt = stmt.where(Source.enabled.is_(True))
            if source_category:
                stmt = stmt.where(Source.source_category == source_category)
            if connector_type:
                stmt = stmt.where(Source.connector_type == connector_type)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def upsert_sources(self, sources: list[SourceConfig]) -> list[Source]:
        if not sources:
            return []

        now = datetime.now(UTC)
        async with self._session_factory() as session:
            keys = [source.source_key for source in sources]
            rows = await session.execute(select(Source).where(Source.source_key.in_(keys)))
            existing = {row.source_key: row for row in rows.scalars().all()}

            for source in sources:
                model = existing.get(source.source_key)
                if model is None:
                    model = Source(
                        source_key=source.source_key,
                        name=source.name,
                        url=source.url,
                        source_type=source.source_type,
                        source_category=source.source_category,
                        connector_type=source.connector_type,
                        terms_url=source.terms_url,
                        legal_basis=source.legal_basis,
                        provider_domain=source.provider_domain,
                        rate_profile=source.rate_profile,
                        requires_api_key=source.requires_api_key,
                        requires_user_agent=source.requires_user_agent,
                        user_agent=source.user_agent,
                        enabled=True if source.enabled is None else source.enabled,
                        crawl_interval_minutes=source.crawl_interval_minutes,
                        rate_limit_per_minute=source.rate_limit_per_minute,
                        retry_policy_json=source.retry_policy or {},
                        parser_contract_json=source.parser_contract or {},
                    )
                    session.add(model)
                    existing[source.source_key] = model

                model.name = source.name
                model.url = source.url
                model.source_type = source.source_type
                model.source_category = source.source_category
                model.connector_type = source.connector_type
                model.terms_url = source.terms_url
                model.legal_basis = source.legal_basis
                model.provider_domain = source.provider_domain
                model.rate_profile = source.rate_profile
                model.requires_api_key = source.requires_api_key
                model.requires_user_agent = source.requires_user_agent
                model.user_agent = source.user_agent
                if source.enabled is not None:
                    model.enabled = source.enabled
                model.crawl_interval_minutes = source.crawl_interval_minutes
                model.rate_limit_per_minute = source.rate_limit_per_minute
                model.retry_policy_json = source.retry_policy or {}
                model.parser_contract_json = source.parser_contract or {}
                model.updated_at = now

            await session.commit()
            refreshed = await session.execute(
                select(Source).where(Source.source_key.in_(keys))
            )
            return list(refreshed.scalars().all())

    async def list_source_map(self, *, enabled_only: bool = False) -> dict[str, Source]:
        sources = await self.list_sources(enabled_only=enabled_only)
        return {str(source.source_key): source for source in sources}

    async def set_enabled(self, identifier: int | str, enabled: bool) -> Source | None:
        async with self._session_factory() as session:
            stmt = select(Source)
            if isinstance(identifier, int):
                stmt = stmt.where(Source.id == identifier)
            else:
                text_identifier = str(identifier).strip()
                if text_identifier.isdigit():
                    stmt = stmt.where(
                        or_(
                            Source.id == int(text_identifier),
                            Source.source_key == text_identifier,
                        )
                    )
                else:
                    stmt = stmt.where(Source.source_key == text_identifier)
            result = await session.execute(stmt)
            source = result.scalar_one_or_none()
            if source is None:
                return None

            source.enabled = enabled
            source.updated_at = datetime.now(UTC)
            await session.commit()
            return source

    async def delete(self, identifier: int | str) -> bool:
        async with self._session_factory() as session:
            stmt = select(Source)
            if isinstance(identifier, int):
                stmt = stmt.where(Source.id == identifier)
            else:
                text_identifier = str(identifier).strip()
                if text_identifier.isdigit():
                    stmt = stmt.where(
                        or_(
                            Source.id == int(text_identifier),
                            Source.source_key == text_identifier,
                        )
                    )
                else:
                    stmt = stmt.where(Source.source_key == text_identifier)
            result = await session.execute(stmt)
            source = result.scalar_one_or_none()
            if source is None:
                return False

            await session.delete(source)
            await session.commit()
            return True


class ArticleRepository:
    """Article persistence and retrieval."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_id(self, article_id: str) -> Article | None:
        async with self._session_factory() as session:
            result = await session.execute(select(Article).where(Article.id == article_id))
            return result.scalar_one_or_none()

    async def list_for_api(
        self,
        *,
        source: str | None = None,
        sentiment: str | None = None,
        topic: str | None = None,
        search: str | None = None,
        published_since: datetime | None = None,
        published_until: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
        sort_by: str | None = None,
        sort_order: str = "desc",
    ) -> list[dict[str, Any]]:
        bounded_limit = max(int(limit), 1)
        bounded_offset = max(int(offset), 0)
        needs_post_filtering = bool(topic or search)

        async with self._session_factory() as session:
            statement = select(Article)
            if source:
                source_match = str(source).strip()
                if not source_match:
                    pass
                elif source_match.isdigit():
                    statement = statement.where(Article.source_id == int(source_match))
                else:
                    source_slug = _slugify(source_match)
                    source_name = source_match.replace("-", " ").strip().lower()
                    statement = statement.where(
                        or_(
                            Article.source_key == source_slug,
                            func.lower(Article.source_name) == source_name,
                        )
                    )
            if sentiment:
                statement = statement.where(Article.sentiment == sentiment)
            if published_since:
                statement = statement.where(Article.published_at >= published_since)
            if published_until:
                statement = statement.where(Article.published_at <= published_until)

            if sort_by == "relevance":
                order_by: Any = Article.market_impact_score.desc().nullslast()
            elif sort_by == "sentiment":
                order_by = Article.sentiment_score.desc().nullslast()
            else:
                order_by = Article.published_at.desc()

            if (sort_order or "desc").lower() == "asc":
                order_by = order_by.asc()

            statement = statement.order_by(order_by)
            if not needs_post_filtering:
                statement = statement.offset(bounded_offset).limit(bounded_limit)
            result = await session.execute(statement)
            articles = list(result.scalars().all())

        payload = [self._to_payload(article) for article in articles]

        if topic:
            topic_slug = _slugify(topic)
            payload = [article for article in payload if _topic_matches(article, topic_slug)]

        if search:
            normalized = _normalize_search_text(search)
            aliases = _collect_aliases(normalized)
            payload = [
                article
                for article in payload
                if _search_match(article, aliases)
            ]

        if needs_post_filtering and bounded_offset:
            payload = payload[bounded_offset:]

        return payload[:bounded_limit]

    async def count_for_api(
        self,
        *,
        source: str | None = None,
        sentiment: str | None = None,
        topic: str | None = None,
        search: str | None = None,
        published_since: datetime | None = None,
        published_until: datetime | None = None,
    ) -> int:
        needs_post_filtering = bool(topic or search)

        async with self._session_factory() as session:
            statement = select(Article)
            if source:
                source_match = str(source).strip()
                if source_match:
                    if source_match.isdigit():
                        statement = statement.where(Article.source_id == int(source_match))
                    else:
                        source_slug = _slugify(source_match)
                        source_name = source_match.replace("-", " ").strip().lower()
                        statement = statement.where(
                            or_(
                                Article.source_key == source_slug,
                                func.lower(Article.source_name) == source_name,
                            )
                        )
            if sentiment:
                statement = statement.where(Article.sentiment == sentiment)
            if published_since:
                statement = statement.where(Article.published_at >= published_since)
            if published_until:
                statement = statement.where(Article.published_at <= published_until)

            if not needs_post_filtering:
                total_stmt = select(func.count()).select_from(statement.subquery())
                total_result = await session.execute(total_stmt)
                return int(total_result.scalar() or 0)

            result = await session.execute(statement)
            articles = list(result.scalars().all())

        payload = [self._to_payload(article) for article in articles]
        if topic:
            topic_slug = _slugify(topic)
            payload = [article for article in payload if _topic_matches(article, topic_slug)]
        if search:
            normalized = _normalize_search_text(search)
            aliases = _collect_aliases(normalized)
            payload = [
                article
                for article in payload
                if _search_match(article, aliases)
            ]
        return len(payload)

    async def get_sources_from_articles(self) -> list[str]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(Article.source_name)
                .distinct()
                .where(and_(Article.source_name.is_not(None), Article.source_name != ""))
            )
            return sorted({row[0] for row in result.all() if row[0]})

    async def get_topics_from_articles(self) -> list[str]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(Article.topics).where(Article.topics.is_not(None))
            )
            seen: set[str] = set()
            topics: list[str] = []
            for row in result.all():
                for item in row[0] or []:
                    if item and item not in seen:
                        seen.add(item)
                        topics.append(item)
            return sorted(topics)

    async def upsert_deduplicated(
        self, run_id: str, items: list[dict[str, Any]]
    ) -> IngestResult:
        if not items:
            return IngestResult(run_id=run_id)

        normalized = []
        for item in items:
            normalized_item = self._normalize_for_db(item)
            if normalized_item:
                normalized.append(normalized_item)

        if not normalized:
            return IngestResult(run_id=run_id)

        url_hashes = [item["url_hash"] for item in normalized]
        dedupe_keys = [item["dedupe_key"] for item in normalized]
        ids = [item["id"] for item in normalized]

        async with self._session_factory() as session:
            existing: set[str] = set()
            if url_hashes:
                existing_url = await session.execute(
                    select(Article.url_hash).where(Article.url_hash.in_(url_hashes))
                )
                existing |= _extract_single_column(existing_url.all(), 0)
            if dedupe_keys:
                existing_dedupe = await session.execute(
                    select(Article.dedupe_key).where(Article.dedupe_key.in_(dedupe_keys))
                )
                existing |= _extract_single_column(existing_dedupe.all(), 0)
            if ids:
                existing_ids = await session.execute(
                    select(Article.id).where(Article.id.in_(ids))
                )
                existing |= _extract_single_column(existing_ids.all(), 0)

            added = 0
            skipped = 0
            inserted_ids: list[str] = []
            for item in normalized:
                if item["url_hash"] in existing or item["dedupe_key"] in existing:
                    skipped += 1
                    continue

                model = Article(
                    id=item["id"],
                    source_id=item["source_id"],
                    source_key=item["source_key"],
                    source_name=item["source_name"],
                    source_item_id=item["source_item_id"],
                    title=item["title"],
                    url=item["url"],
                    url_hash=item["url_hash"],
                    dedupe_key=item["dedupe_key"],
                    published_at=item["published_at"],
                    summarized_headline=item["summarized_headline"],
                    summary_bullets=item["summary_bullets"],
                    sentiment=item["sentiment"],
                    sentiment_score=item["sentiment_score"],
                    market_impact_score=item["market_impact_score"],
                    key_entities=item["key_entities"],
                    topics=item["topics"],
                    content=item["content"],
                    ingestion_run_id=run_id,
                )
                session.add(model)
                inserted_ids.append(item["id"])
                existing.add(item["url_hash"])
                existing.add(item["dedupe_key"])
                added += 1

            if inserted_ids:
                created = []
                now = datetime.now(UTC)
                for item in normalized:
                    if item["id"] not in inserted_ids:
                        continue
                    created.append(
                        ArticleDedupe(
                            article_id=item["id"],
                            source_id=item["source_id"],
                            key_type="url_hash",
                            key_value=item["url_hash"],
                            created_at=now,
                        )
                    )
                    created.append(
                        ArticleDedupe(
                            article_id=item["id"],
                            source_id=item["source_id"],
                            key_type="dedupe_key",
                            key_value=item["dedupe_key"],
                            created_at=now,
                        )
                    )
                session.add_all(created)

            await session.commit()

            return IngestResult(
                run_id=run_id,
                requested_sources=0,
                items_seen=len(normalized),
                items_stored=added,
                items_skipped=skipped,
            )

    async def count(self) -> int:
        async with self._session_factory() as session:
            result = await session.execute(select(func.count(Article.id)))
            return int(result.scalar() or 0)

    @staticmethod
    def _normalize_for_db(item: dict[str, Any]) -> dict[str, Any] | None:
        title = _normalize_title_value(item.get("title"))
        if not title:
            return None

        source_name = str(item.get("source") or item.get("source_name") or "Unknown").strip()
        source_key = _slugify(source_name)

        published_at = _coerce_datetime(item.get("published_at"))
        url = str(item.get("url") or "").strip()
        canonical_url = _canonicalize_url(url)
        url_hash = _hash_value(
            canonical_url
            if canonical_url
            else f"{source_key}|{title}|{published_at.isoformat()}"
        )
        # dedupe_key: drop source_key and use YYYY-MM-DD to deduplicate identical titles across sources
        # on the same day, significantly improving ranking/dedup quality.
        day_str = published_at.strftime("%Y-%m-%d") if published_at else "1970-01-01"
        dedupe_key = _hash_value(f"{title.lower()}|{day_str}")
        article_id = item.get("id")
        if not article_id:
            article_id = _hash_value(
                f"{source_key}|{title}|{canonical_url}|{published_at.isoformat()}"
            )

        source_id = item.get("source_id")
        source_id_int = source_id if isinstance(source_id, int) else None

        return {
            "id": str(article_id),
            "source_id": source_id_int,
            "source_key": source_key,
            "source_name": source_name,
            "source_item_id": (
                str(item.get("source_item_id"))
                if item.get("source_item_id") is not None
                else None
            ),
            "title": title,
            "url": canonical_url,
            "url_hash": url_hash,
            "dedupe_key": dedupe_key,
            "published_at": published_at,
            "summarized_headline": _coerce_opt_str(item.get("summarized_headline")),
            "summary_bullets": _coerce_list(item.get("summary_bullets")),
            "sentiment": _coerce_opt_str(item.get("sentiment")),
            "sentiment_score": _safe_float(item.get("sentiment_score")),
            "market_impact_score": _safe_float(item.get("market_impact_score")),
            "key_entities": _coerce_list(item.get("key_entities")),
            "topics": _coerce_list(item.get("topics")),
            "content": str(item.get("content") or "").strip(),
        }

    @staticmethod
    def _to_payload(article: Article) -> dict[str, Any]:
        return {
            "id": article.id,
            "title": article.title,
            "url": article.url,
            "source": article.source_name,
            "published_at": article.published_at.isoformat(),
            "summarized_headline": article.summarized_headline,
            "summary_bullets": article.summary_bullets or [],
            "sentiment": article.sentiment,
            "sentiment_score": article.sentiment_score,
            "market_impact_score": article.market_impact_score,
            "key_entities": article.key_entities or [],
            "topics": article.topics or [],
        }


class IngestionRunRepository:
    """Run tracking with counters and per-source status."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_run(self, run_id: str, requested_sources: int) -> None:
        async with self._session_factory() as session:
            session.add(
                IngestionRun(
                    run_id=run_id,
                    requested_sources=requested_sources,
                    status="running",
                    started_at=datetime.now(UTC),
                    error_summary=[],
                    source_results=[],
                )
            )
            await session.commit()

    async def update(self, run_id: str, **fields: Any) -> None:
        if not fields:
            return
        async with self._session_factory() as session:
            run = await session.get(IngestionRun, run_id)
            if run is None:
                return
            for key, value in fields.items():
                setattr(run, key, value)
            await session.commit()

    async def finish_run(
        self,
        run_id: str,
        *,
        items_seen: int,
        items_stored: int,
        items_skipped: int,
        failed_sources: int,
        source_errors: int,
        error_summary: list[str],
        source_results: list[dict[str, Any]],
        status: str = "completed",
    ) -> None:
        async with self._session_factory() as session:
            run = await session.get(IngestionRun, run_id)
            if run is None:
                return
            run.finished_at = datetime.now(UTC)
            run.items_seen = items_seen
            run.items_stored = items_stored
            run.items_skipped = items_skipped
            run.failed_sources = failed_sources
            run.source_errors = source_errors
            run.error_summary = error_summary
            run.source_results = source_results
            run.status = status
            if run.finished_at:
                run.latency_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
            await session.commit()

    async def get(self, run_id: str) -> IngestionRun | None:
        async with self._session_factory() as session:
            return await session.get(IngestionRun, run_id)


class IngestionStateRepository:
    """Source cursor and failure-state tracker."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_all(self) -> list[IngestionState]:
        async with self._session_factory() as session:
            result = await session.execute(select(IngestionState))
            return list(result.scalars().all())

    async def get_for_source(self, source_id: int) -> IngestionState | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(IngestionState).where(IngestionState.source_id == source_id)
            )
            return result.scalar_one_or_none()

    async def ensure_state(self, source_id: int) -> IngestionState:
        async with self._session_factory() as session:
            existing = await session.execute(
                select(IngestionState).where(IngestionState.source_id == source_id)
            )
            state = existing.scalar_one_or_none()
            if state is None:
                state = IngestionState(source_id=source_id)
                session.add(state)
                await session.commit()
            return state

    async def mark_source_success(
        self,
        source_id: int,
        *,
        cursor_type: str,
        cursor_value: str | None,
        last_published_at: datetime | None,
        latency_ms: int,
        etag: str | None = None,
    ) -> None:
        async with self._session_factory() as session:
            state = await self._load_or_init_state(session, source_id)
            state.cursor_type = cursor_type
            state.cursor_value = cursor_value
            state.etag = etag
            state.last_published_at = last_published_at
            state.last_success_at = datetime.now(UTC)
            state.last_latency_ms = latency_ms
            state.last_failure_at = None
            state.last_error = None
            state.consecutive_failures = 0
            state.disabled_by_failure = False
            state.next_retry_at = None
            await session.commit()

    async def mark_source_failure(
        self,
        source_id: int,
        *,
        error: str,
        cursor_type: str,
        cursor_value: str | None,
        latency_ms: int,
        base_delay_seconds: int = 15,
        max_delay_seconds: int = 600,
        jitter_ms: int = 0,
    ) -> None:
        async with self._session_factory() as session:
            state = await self._load_or_init_state(session, source_id)
            state.consecutive_failures = (state.consecutive_failures or 0) + 1
            delay_seconds = min(
                base_delay_seconds * (2 ** (state.consecutive_failures - 1)),
                max_delay_seconds,
            )
            if jitter_ms > 0:
                jitter = min(jitter_ms / 1000, delay_seconds * 0.2)
                delay_seconds += random.uniform(0.0, jitter)
            state.next_retry_at = datetime.now(UTC) + timedelta(
                seconds=delay_seconds
            )
            state.last_failure_at = datetime.now(UTC)
            state.last_error = error
            state.last_latency_ms = latency_ms
            state.cursor_type = cursor_type
            state.cursor_value = cursor_value
            state.disabled_by_failure = True
            await session.commit()

    async def _load_or_init_state(
        self,
        session: AsyncSession,
        source_id: int,
    ) -> IngestionState:
        existing = await session.execute(
            select(IngestionState).where(IngestionState.source_id == source_id)
        )
        state = existing.scalar_one_or_none()
        if state is None:
            state = IngestionState(source_id=source_id)
            session.add(state)
            await session.flush()
        return state


class UserArticleStateRepository:
    """User-level article bookmark state."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save_article(
        self, *, user_id: str, article_id: str, snapshot: dict[str, Any]
    ) -> None:
        async with self._session_factory() as session:
            existing = await session.get(UserSavedArticle, (user_id, article_id))
            if existing is None:
                session.add(
                    UserSavedArticle(
                        user_id=user_id,
                        article_id=article_id,
                        article_snapshot=snapshot,
                    )
                )
            else:
                existing.article_snapshot = snapshot
                existing.saved_at = datetime.now(UTC)
            await session.commit()

    async def unsave_article(self, user_id: str, article_id: str) -> bool:
        async with self._session_factory() as session:
            result = await session.execute(
                delete(UserSavedArticle).where(
                    and_(
                        UserSavedArticle.user_id == user_id,
                        UserSavedArticle.article_id == article_id,
                    )
                )
            )
            await session.commit()
            return bool(getattr(result, "rowcount", 0))

    async def is_saved(self, user_id: str, article_id: str) -> bool:
        async with self._session_factory() as session:
            result = await session.execute(
                select(UserSavedArticle.article_id).where(
                    and_(
                        UserSavedArticle.user_id == user_id,
                        UserSavedArticle.article_id == article_id,
                    )
                )
            )
            return result.scalar_one_or_none() is not None

    async def list_saved(self, user_id: str) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            rows = await session.execute(
                select(UserSavedArticle).where(UserSavedArticle.user_id == user_id)
            )
            items: list[dict[str, Any]] = []
            for row in rows.scalars().all():
                payload = row.article_snapshot if isinstance(row.article_snapshot, dict) else {}
                payload = dict(payload)
                payload["id"] = row.article_id
                payload["saved_at"] = row.saved_at.isoformat()
                items.append(payload)
            return items


class UserSettingsRepository:
    """Persisted settings preferences per user."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get(self, user_id: str) -> dict[str, Any] | None:
        async with self._session_factory() as session:
            existing = await session.get(UserSettings, user_id)
            if existing is None:
                return None
            payload = existing.settings_json
            return payload if isinstance(payload, dict) else {}

    async def upsert(self, user_id: str, settings: dict[str, Any]) -> dict[str, Any]:
        async with self._session_factory() as session:
            existing = await session.get(UserSettings, user_id)
            if existing is None:
                existing = UserSettings(user_id=user_id, settings_json=dict(settings))
                session.add(existing)
            else:
                existing.settings_json = dict(settings)
                existing.updated_at = datetime.now(UTC)
            await session.commit()
            return dict(settings)


class UserAlertPreferencesRepository:
    """Persisted alert preferences per user."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get(self, user_id: str) -> dict[str, Any] | None:
        async with self._session_factory() as session:
            existing = await session.get(UserAlertPreferences, user_id)
            if existing is None:
                return None
            payload = existing.alerts_json
            return payload if isinstance(payload, dict) else {}

    async def upsert(self, user_id: str, alerts: dict[str, Any]) -> dict[str, Any]:
        async with self._session_factory() as session:
            existing = await session.get(UserAlertPreferences, user_id)
            if existing is None:
                existing = UserAlertPreferences(user_id=user_id, alerts_json=dict(alerts))
                session.add(existing)
            else:
                existing.alerts_json = dict(alerts)
                existing.updated_at = datetime.now(UTC)
            await session.commit()
            return dict(alerts)
