"""Abstract base for all financial news connectors.

Every connector lives in ``src/financial_news/services/connectors/`` and must
subclass :class:`BaseConnector`.  The continuous runner will auto-discover any
concrete subclass and include it in its ingestion cycle.

Implementing a new connector is straightforward:

    class MySourceConnector(BaseConnector):
        name = "My Source"
        requires_api_key = False

        async def fetch_articles(self, source_id=None):
            ...  # return list[dict[str, Any]]
"""

from __future__ import annotations

import abc
from typing import Any

class BaseConnector(abc.ABC):
    """Contract that every data-source connector must satisfy."""

    # ---- required class-level attributes ----

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable name shown in logs and the admin panel."""
        ...

    @property
    @abc.abstractmethod
    def requires_api_key(self) -> bool:
        """Whether this connector needs an API key to function."""
        ...

    # ---- required async method ----

    @abc.abstractmethod
    async def fetch_articles(
        self,
        source_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch article payloads accepted by the ingestion contract validator.

        Each dict should contain at minimum::

            {
                "id": str,             # unique hash
                "title": str,
                "url": str,
                "content": str,
                "published_at": datetime,
                "source": str,
                "sentiment": str,
                "sentiment_score": float,
                "key_entities": list[str],
                "topics": list[str],
            }
        The continuous runner normalizes these payloads to
        ``ArticleIngestRecord`` before writes.
        """
        ...

    # ---- optional hooks ----

    async def healthcheck(self) -> bool:
        """Return True if the connector can reach its data source.

        Override for richer health checks; the default simply returns True.
        """
        return True

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self.name!r}>"
