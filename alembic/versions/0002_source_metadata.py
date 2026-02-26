"""Add rich source metadata fields for connector governance."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_source_metadata"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("source_category", sa.String(length=64), nullable=True))
    op.add_column("sources", sa.Column("connector_type", sa.String(length=64), nullable=True))
    op.add_column("sources", sa.Column("terms_url", sa.Text(), nullable=True))
    op.add_column("sources", sa.Column("legal_basis", sa.String(length=128), nullable=True))
    op.add_column("sources", sa.Column("provider_domain", sa.String(length=255), nullable=True))
    op.add_column("sources", sa.Column("rate_profile", sa.String(length=64), nullable=True))
    op.add_column(
        "sources",
        sa.Column(
            "requires_api_key",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "sources",
        sa.Column(
            "requires_user_agent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column("sources", sa.Column("user_agent", sa.String(length=255), nullable=True))

    op.create_index("ix_sources_source_category", "sources", ["source_category"])
    op.create_index("ix_sources_connector_type", "sources", ["connector_type"])


def downgrade() -> None:
    op.drop_index("ix_sources_connector_type", table_name="sources")
    op.drop_index("ix_sources_source_category", table_name="sources")

    op.drop_column("sources", "user_agent")
    op.drop_column("sources", "requires_user_agent")
    op.drop_column("sources", "requires_api_key")
    op.drop_column("sources", "rate_profile")
    op.drop_column("sources", "provider_domain")
    op.drop_column("sources", "legal_basis")
    op.drop_column("sources", "terms_url")
    op.drop_column("sources", "connector_type")
    op.drop_column("sources", "source_category")
