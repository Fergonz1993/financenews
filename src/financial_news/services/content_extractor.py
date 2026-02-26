"""Lightweight HTTP-based content extractor — replaces Puppeteer dependency.

Uses httpx + HTML parsing to extract article text from web pages. No browser
needed — 10x faster and works on servers without Chrome installed.

Falls back gracefully: RSS full-text → HTTP fetch + <p> extraction → skip.
"""

from __future__ import annotations

import html
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_P_TAG_RE = re.compile(r"<p\b[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)
_ARTICLE_TAG_RE = re.compile(
    r"<(?:article|main|div[^>]*class=[\"'][^\"']*(?:article|content|post|entry|story)[^\"']*[\"'])[^>]*>(.*?)</(?:article|main|div)>",
    re.IGNORECASE | re.DOTALL,
)
_SCRIPT_STYLE_RE = re.compile(
    r"<(?:script|style)[^>]*>.*?</(?:script|style)>", re.IGNORECASE | re.DOTALL
)
# Common tracking parameters to strip from URLs
_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "ref_", "source", "sessionid", "fbclid", "gclid", "dclid",
    "msclkid", "twclid", "igshid",
})


def clean_html_to_text(raw_html: str) -> str:
    """Strip HTML tags, collapse whitespace, unescape entities."""
    # Remove script/style blocks first
    cleaned = _SCRIPT_STYLE_RE.sub("", raw_html)
    # Strip remaining tags
    text = _TAG_RE.sub(" ", html.unescape(cleaned))
    return _WS_RE.sub(" ", text).strip()


def canonicalize_url(url: str) -> str:
    """Strip tracking parameters from a URL for dedup purposes."""
    from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

    if not url:
        return ""
    try:
        parsed = urlparse(url)
        cleaned_params = [
            (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if k.lower() not in _TRACKING_PARAMS
            and not k.lower().endswith("clid")
        ]
        rebuilt = parsed._replace(
            query=urlencode(cleaned_params) if cleaned_params else "",
            fragment="",
        )
        return urlunparse(rebuilt).rstrip("/")
    except Exception:
        return url.split("?")[0].split("#")[0].rstrip("/")


def normalize_title_hash(title: str) -> str:
    """Create a normalized hash key from the title for fuzzy dedup."""
    import hashlib
    # Lowercase, strip punctuation, collapse whitespace
    normalized = re.sub(r"[^a-z0-9\s]", "", title.lower())
    normalized = _WS_RE.sub(" ", normalized).strip()
    return hashlib.sha256(normalized.encode()).hexdigest()[:24]


class ContentExtractor:
    """Extract article text from web pages via HTTP (no browser needed)."""

    DEFAULT_TIMEOUT = 10.0
    DEFAULT_MAX_CHARS = 5000
    DEFAULT_USER_AGENT = "finnews-extractor/1.0 (+https://example.com/finnews)"

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        max_chars: int = DEFAULT_MAX_CHARS,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.timeout = timeout
        self.max_chars = max_chars
        self.user_agent = user_agent

    async def extract(self, url: str) -> str | None:
        """Fetch a URL and extract article text. Returns None on failure."""
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": self.user_agent},
            ) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.debug("ContentExtractor: HTTP %d for %s", resp.status_code, url)
                    return None
                return self._extract_from_html(resp.text)
        except Exception as exc:
            logger.debug("ContentExtractor: error fetching %s: %s", url, exc)
            return None

    def _extract_from_html(self, raw_html: str) -> str | None:
        """Extract article text from HTML using a fallback chain."""
        if not raw_html:
            return None

        # Strategy 1: Find <article> or main content div
        article_match = _ARTICLE_TAG_RE.search(raw_html)
        if article_match:
            content = article_match.group(1)
            paragraphs = _P_TAG_RE.findall(content)
            if paragraphs:
                text = " ".join(clean_html_to_text(p) for p in paragraphs)
                if len(text) > 100:
                    return text[:self.max_chars]

        # Strategy 2: Extract all <p> tags from the page
        paragraphs = _P_TAG_RE.findall(raw_html)
        if paragraphs:
            # Filter out very short paragraphs (likely UI elements)
            meaningful = [
                clean_html_to_text(p) for p in paragraphs
                if len(clean_html_to_text(p)) > 30
            ]
            if meaningful:
                text = " ".join(meaningful)
                return text[:self.max_chars]

        # Strategy 3: Brute force — strip all HTML
        text = clean_html_to_text(raw_html)
        if len(text) > 100:
            return text[:self.max_chars]

        return None

    async def extract_batch(
        self,
        urls: list[str],
        *,
        concurrency: int = 5,
    ) -> dict[str, str | None]:
        """Extract content from multiple URLs with bounded concurrency."""
        import asyncio

        semaphore = asyncio.Semaphore(concurrency)
        results: dict[str, str | None] = {}

        async def _fetch_one(url: str) -> None:
            async with semaphore:
                results[url] = await self.extract(url)

        await asyncio.gather(*[_fetch_one(url) for url in urls])
        return results
