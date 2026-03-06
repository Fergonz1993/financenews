"""Public source connectors for financial news ingestion.

Each connector implements a `fetch_articles()` coroutine that returns a list of
dicts compatible with `ArticleRepository.upsert_deduplicated`.
"""

from .base import BaseConnector
from .gdelt import GDELTConnector
from .newsdata import NewsdataConnector
from .reddit import RedditFinanceConnector
from .sec_edgar import SECEdgarConnector

__all__ = [
    "BaseConnector",
    "GDELTConnector",
    "NewsdataConnector",
    "RedditFinanceConnector",
    "SECEdgarConnector",
]


