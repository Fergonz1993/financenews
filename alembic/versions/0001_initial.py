"""Initial PostgreSQL schema for finance news ingestion."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_key", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="rss"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("crawl_interval_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("retry_policy_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("parser_contract_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.UniqueConstraint("source_key", name="ux_sources_source_key"),
    )
    op.create_index("ix_sources_enabled", "sources", ["enabled"])
    op.create_index("ix_sources_source_key", "sources", ["source_key"])

    op.create_table(
        "articles",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_key", sa.String(length=128), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_item_id", sa.String(length=255), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("url_hash", sa.String(length=64), nullable=False),
        sa.Column("dedupe_key", sa.String(length=64), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summarized_headline", sa.Text(), nullable=True),
        sa.Column("summary_bullets", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("sentiment", sa.String(length=32), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("market_impact_score", sa.Float(), nullable=True),
        sa.Column("key_entities", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("topics", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("ingestion_run_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url_hash"),
        sa.UniqueConstraint("dedupe_key"),
    )
    op.create_index("ix_articles_published_at", "articles", ["published_at"])
    op.create_index("ix_articles_source", "articles", ["source_id"])
    op.create_index("ix_articles_source_name", "articles", ["source_name"])
    op.create_index("ix_articles_sentiment", "articles", ["sentiment"])
    op.create_index("ix_articles_topic", "articles", ["topics"], postgresql_using="gin")
    op.create_index("ix_articles_entities", "articles", ["key_entities"], postgresql_using="gin")

    op.create_table(
        "article_dedupe",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("article_id", sa.String(length=64), sa.ForeignKey("articles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("key_type", sa.String(length=64), nullable=False),
        sa.Column("key_value", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.UniqueConstraint("key_type", "key_value", name="uq_article_dedupe_key"),
    )
    op.create_index("ix_article_dedupe_key_value", "article_dedupe", ["key_type", "key_value"])

    op.create_table(
        "ingestion_runs",
        sa.Column("run_id", sa.String(length=64), primary_key=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
        sa.Column("requested_sources", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_stored", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_sources", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source_results", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "ingestion_state",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cursor_type", sa.String(length=64), nullable=False, server_default="published_at"),
        sa.Column("cursor_value", sa.Text(), nullable=True),
        sa.Column("etag", sa.String(length=255), nullable=True),
        sa.Column("last_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_latency_ms", sa.Integer(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_by_failure", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.UniqueConstraint("source_id", name="ux_ingestion_state_source"),
    )
    op.create_index("ix_ingestion_state_source_id", "ingestion_state", ["source_id"])

    op.create_table(
        "user_saved_articles",
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("article_id", sa.String(length=64), sa.ForeignKey("articles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("article_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column(
            "saved_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id", "article_id"),
    )
    op.create_index("ix_user_saved_articles_article", "user_saved_articles", ["article_id"])


def downgrade() -> None:
    op.drop_index("ix_user_saved_articles_article", table_name="user_saved_articles")
    op.drop_table("user_saved_articles")

    op.drop_index("ix_ingestion_state_source_id", table_name="ingestion_state")
    op.drop_table("ingestion_state")

    op.drop_table("ingestion_runs")

    op.drop_index("ix_article_dedupe_key_value", table_name="article_dedupe")
    op.drop_table("article_dedupe")

    op.drop_index("ix_articles_entities", table_name="articles")
    op.drop_index("ix_articles_topic", table_name="articles")
    op.drop_index("ix_articles_sentiment", table_name="articles")
    op.drop_index("ix_articles_source_name", table_name="articles")
    op.drop_index("ix_articles_source", table_name="articles")
    op.drop_index("ix_articles_published_at", table_name="articles")
    op.drop_table("articles")

    op.drop_index("ix_sources_source_key", table_name="sources")
    op.drop_index("ix_sources_enabled", table_name="sources")
    op.drop_table("sources")
