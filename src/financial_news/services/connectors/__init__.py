"""Public source connectors for financial news ingestion.

Each connector implements a `fetch_articles()` coroutine that returns a list of
dicts compatible with `ArticleRepository.upsert_deduplicated`.
"""

from .gdelt import GDELTConnector
from .sec_edgar import SECEdgarConnector
from .newsdata import NewsdataConnector

__all__ = [
    "GDELTConnector",
    "SECEdgarConnector",
    "NewsdataConnector",
]
