#!/usr/bin/env python3
"""Unit tests for the content extractor and URL utilities."""

import pytest

from financial_news.services.content_extractor import (
    ContentExtractor,
    canonicalize_url,
    clean_html_to_text,
    normalize_title_hash,
)


class TestCleanHtmlToText:
    def test_strips_tags(self):
        assert clean_html_to_text("<p>Hello <b>World</b></p>") == "Hello World"

    def test_collapses_whitespace(self):
        assert clean_html_to_text("  hello   world  ") == "hello world"

    def test_unescapes_entities(self):
        assert clean_html_to_text("AT&amp;T &amp; Verizon") == "AT&T & Verizon"

    def test_removes_script_tags(self):
        html = "<p>Text</p><script>alert('xss')</script><p>More</p>"
        result = clean_html_to_text(html)
        assert "alert" not in result
        assert "Text" in result
        assert "More" in result

    def test_removes_style_tags(self):
        html = "<style>.foo{color:red}</style><p>Real content</p>"
        result = clean_html_to_text(html)
        assert "color" not in result
        assert "Real content" in result


class TestCanonicalizeUrl:
    def test_strips_utm_params(self):
        url = "https://example.com/article?utm_source=twitter&utm_medium=social&id=123"
        result = canonicalize_url(url)
        assert "utm_source" not in result
        assert "utm_medium" not in result
        assert "id=123" in result

    def test_strips_fbclid(self):
        url = "https://example.com/page?fbclid=abc123"
        result = canonicalize_url(url)
        assert "fbclid" not in result

    def test_strips_fragment(self):
        url = "https://example.com/article#section-2"
        result = canonicalize_url(url)
        assert "#" not in result

    def test_strips_trailing_slash(self):
        url = "https://example.com/article/"
        result = canonicalize_url(url)
        assert not result.endswith("/")

    def test_preserves_meaningful_params(self):
        url = "https://example.com/article?page=2&category=finance"
        result = canonicalize_url(url)
        assert "page=2" in result
        assert "category=finance" in result

    def test_empty_url(self):
        assert canonicalize_url("") == ""

    def test_identical_urls_match(self):
        url1 = "https://example.com/article?utm_source=twitter"
        url2 = "https://example.com/article?utm_source=facebook"
        assert canonicalize_url(url1) == canonicalize_url(url2)


class TestNormalizeTitleHash:
    def test_same_title_same_hash(self):
        h1 = normalize_title_hash("Market surges on strong earnings")
        h2 = normalize_title_hash("Market surges on strong earnings")
        assert h1 == h2

    def test_case_insensitive(self):
        h1 = normalize_title_hash("Market Surges")
        h2 = normalize_title_hash("market surges")
        assert h1 == h2

    def test_ignores_punctuation(self):
        h1 = normalize_title_hash("Market surges!")
        h2 = normalize_title_hash("Market surges")
        assert h1 == h2

    def test_different_titles_different_hash(self):
        h1 = normalize_title_hash("Market surges on earnings")
        h2 = normalize_title_hash("Market falls on weak data")
        assert h1 != h2

    def test_fixed_length(self):
        h = normalize_title_hash("Any title here")
        assert len(h) == 24


class TestContentExtractor:
    def test_extract_from_html_article_tag(self):
        extractor = ContentExtractor()
        html = """
        <html><body>
        <nav>Navigation stuff</nav>
        <article>
            <h1>Title</h1>
            <p>This is the first paragraph of the article content that is long enough to pass the filter.</p>
            <p>This is the second paragraph providing more details about the story and its implications.</p>
        </article>
        <footer>Footer stuff</footer>
        </body></html>
        """
        result = extractor._extract_from_html(html)
        assert result is not None
        assert "first paragraph" in result
        assert "second paragraph" in result

    def test_extract_from_html_p_tag_fallback(self):
        extractor = ContentExtractor()
        html = """
        <html><body>
        <div>
            <p>This is a very meaningful paragraph about financial markets and their performance over the past quarter.</p>
            <p>Another important paragraph with details about earnings reports and guidance from major corporations.</p>
        </div>
        </body></html>
        """
        result = extractor._extract_from_html(html)
        assert result is not None
        assert "financial markets" in result

    def test_extract_from_html_empty(self):
        extractor = ContentExtractor()
        assert extractor._extract_from_html("") is None

    def test_extract_from_html_too_short(self):
        extractor = ContentExtractor()
        html = "<p>Hi</p>"
        result = extractor._extract_from_html(html)
        # "Hi" is only 2 chars, below 30-char filter for p tags
        # Falls through to brute force, but still too short (< 100)
        assert result is None

    def test_max_chars_respected(self):
        extractor = ContentExtractor(max_chars=50)
        html = "<p>" + "word " * 100 + "</p>"
        result = extractor._extract_from_html(html)
        assert result is not None
        assert len(result) <= 50
