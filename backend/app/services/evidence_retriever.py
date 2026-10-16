import logging
import os
import re
import inspect
from typing import Any

import httpx
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

GNEWS_API_URL = "https://gnews.io/api/v4/search"
GDELT_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

DEFAULT_LIMIT = 3
MAX_LIMIT = 5
REQUEST_TIMEOUT = 15.0
GDELT_TIMEOUT = httpx.Timeout(connect=5.0, read=8.0, write=5.0, pool=5.0)

EvidenceItem = dict[str, str]


def _search_provider(
    provider: Any,
    query: str,
    limit: int,
    diagnostics: dict[str, str] | None,
) -> list[EvidenceItem]:
    if diagnostics is not None and "diagnostics" in inspect.signature(provider).parameters:
        return provider(query, limit, diagnostics=diagnostics)
    return provider(query, limit)

_QUERY_FILLER_WORDS = {
    "a",
    "an",
    "and",
    "announced",
    "according",
    "as",
    "at",
    "by",
    "confirmed",
    "for",
    "from",
    "had",
    "has",
    "have",
    "in",
    "is",
    "of",
    "on",
    "new",
    "reported",
    "reports",
    "said",
    "says",
    "stated",
    "state",
    "states",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "exists",
    "exist",
    "claiming",
    "claims",
    "claimed",
}


def _normalise_limit(limit: int) -> int:
    """Return a safe article limit."""
    try:
        return max(1, min(int(limit), MAX_LIMIT))
    except (TypeError, ValueError):
        return DEFAULT_LIMIT


def _clean_text(value: Any) -> str:
    """Return stripped text, or an empty string for invalid values."""
    return value.strip() if isinstance(value, str) else ""


def _canonical_url(url: str) -> str:
    """Canonicalize a URL for deduplication."""
    clean = _clean_text(url)
    if not clean:
        return ""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(clean)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/")
        return f"{scheme}://{netloc}{path}"
    except Exception:
        return clean


def _sanitize_gnews_query(query: str) -> str:
    """Sanitize query for GNews search syntax.

    Removes possessives, hyphens, and punctuation that cause GNews
    HTTP 400 syntax errors while preserving alphanumeric search keywords.
    """
    clean = re.sub(r"['’]s\b", "", query)
    clean = re.sub(r"[^A-Za-z0-9\s]", " ", clean)
    return " ".join(clean.split())[:200]


def _broaden_query(query: str) -> str:
    """Remove reporting language while retaining entities and key details."""
    clean = re.sub(r"['’]s\b", "", query)
    tokens = re.findall(r"[A-Za-z0-9]+", clean)
    meaningful_tokens = [
        token
        for token in tokens
        if (
            token.lower() not in _QUERY_FILLER_WORDS
            or token[0].isupper()
            or any(character.isdigit() for character in token)
        )
    ]

    # For long claims, focus on named entities, numbers, and core nouns (up to 4 tokens)
    # to avoid empty results in strict AND-based news search APIs.
    if len(meaningful_tokens) > 4:
        entities = [
            t for t in meaningful_tokens
            if t[0].isupper() or any(c.isdigit() for c in t)
        ]
        others = [t for t in meaningful_tokens if t not in entities]
        selected = set(entities + others[:max(0, 4 - len(entities))])
        meaningful_tokens = [t for t in meaningful_tokens if t in selected]

    return " ".join(meaningful_tokens)[:200]



def _normalise_article(
    title: Any,
    url: Any,
    source: Any,
) -> EvidenceItem | None:
    """Convert a provider result to TND's evidence format."""

    title = _clean_text(title)
    url = _clean_text(url)
    source = _clean_text(source)

    if not title or not url:
        return None

    # Only accept HTTP(S) article URLs.
    if not url.startswith(("https://", "http://")):
        return None

    return {
        "source": source or "News publisher",
        "description": title,
        "url": url,
    }



def search_gnews(
    query: str,
    limit: int = DEFAULT_LIMIT,
    diagnostics: dict[str, str] | None = None,
) -> list[EvidenceItem]:
    """Search GNews for related news articles.

    Articles provide leads for further verification; they do not
    independently prove that a claim is true.
    """

    query = _clean_text(query)

    if not query:
        return []

    api_key = os.getenv("GNEWS_API_KEY", "").strip()
    if diagnostics is not None:
        diagnostics["gnews"] = "configured" if api_key else "not_configured"

    if not api_key:
        logger.warning(
            "GNews API key is missing. Configure GNEWS_API_KEY in the environment."
        )
        return []

    sanitized_query = _sanitize_gnews_query(query)
    if not sanitized_query:
        return []

    params = {
        "q": sanitized_query,
        "lang": "en",
        "max": _normalise_limit(limit),
        "apikey": api_key,
    }

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            response = client.get(
                GNEWS_API_URL,
                params=params,
            )
            response.raise_for_status()

        try:
            data = response.json()
        except ValueError:
            logger.warning("GNews returned invalid JSON.")
            return []

        if not isinstance(data, dict):
            logger.warning("GNews returned an unexpected response.")
            return []

        articles = data.get("articles", [])

        if not isinstance(articles, list):
            logger.warning("GNews articles field is not a list.")
            return []

        evidence: list[EvidenceItem] = []
        seen_urls: set[str] = set()

        for article in articles:
            if not isinstance(article, dict):
                continue

            publisher = article.get("source")

            if not isinstance(publisher, dict):
                publisher = {}

            item = _normalise_article(
                title=article.get("title"),
                url=article.get("url"),
                source=publisher.get("name"),
            )

            if item:
                canon = _canonical_url(item["url"])
                if canon and canon not in seen_urls:
                    seen_urls.add(canon)
                    evidence.append(item)

            if len(evidence) >= _normalise_limit(limit):
                break

        logger.info(
            "GNews returned %d usable article(s).",
            len(evidence),
        )

        return evidence

    except httpx.HTTPStatusError as exc:
        # Do not log the full request URL because it contains the API key.
        logger.warning(
            "GNews returned HTTP %s.",
            exc.response.status_code,
        )

    except httpx.RequestError as exc:
        logger.warning(
            "GNews network request failed: %s",
            type(exc).__name__,
        )

    return []


def search_gdelt(
    query: str,
    limit: int = DEFAULT_LIMIT,
) -> list[EvidenceItem]:
    """Search GDELT for related news articles."""

    query = _clean_text(query)

    if not query:
        return []

    # Clean query text for GDELT doc API
    clean_q = re.sub(r"['’]s\b", "", query)
    clean_q = re.sub(r"[^\w\s-]", " ", clean_q)
    clean_q = " ".join(clean_q.split())[:300]

    if not clean_q:
        return []

    params = {
        "query": clean_q,
        "mode": "artlist",
        "format": "json",
        "maxrecords": _normalise_limit(limit),
        "timespan": "3months",
        "sort": "hybridrel",
    }

    try:
        with httpx.Client(
            timeout=GDELT_TIMEOUT,
            follow_redirects=True,
        ) as client:
            response = client.get(
                GDELT_API_URL,
                params=params,
                headers={
                    "User-Agent": "TND-NewsDetector/0.1"
                },
            )
            response.raise_for_status()

        try:
            data = response.json()
        except ValueError:
            logger.warning(
                "GDELT returned a non-JSON response (HTTP %s).",
                response.status_code,
            )
            return []

        if not isinstance(data, dict):
            logger.warning("GDELT returned an unexpected response.")
            return []

        articles = data.get("articles", [])

        if not isinstance(articles, list):
            logger.warning("GDELT articles field is not a list.")
            return []

        evidence: list[EvidenceItem] = []
        seen_urls: set[str] = set()

        for article in articles:
            if not isinstance(article, dict):
                continue

            item = _normalise_article(
                title=article.get("title"),
                url=article.get("url"),
                source=article.get("domain"),
            )

            if item:
                canon = _canonical_url(item["url"])
                if canon and canon not in seen_urls:
                    seen_urls.add(canon)
                    evidence.append(item)

            if len(evidence) >= _normalise_limit(limit):
                break

        logger.info(
            "GDELT returned %d usable article(s).",
            len(evidence),
        )

        return evidence

    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            retry_after = exc.response.headers.get("Retry-After")
            logger.warning(
                "GDELT returned HTTP 429 (rate limited). Retry-After: %s",
                retry_after,
            )
        else:
            logger.warning(
                "GDELT returned HTTP %s.",
                exc.response.status_code,
            )

    except httpx.RequestError as exc:
        logger.warning(
            "GDELT network request failed: %s",
            type(exc).__name__,
        )

    return []


def search_evidence(
    query: str,
    limit: int = DEFAULT_LIMIT,
    cache: dict[str, list[EvidenceItem]] | None = None,
    diagnostics: dict[str, str] | None = None,
) -> list[EvidenceItem]:
    """Search GNews directly and broadly, then use GDELT as a fallback."""

    query = _clean_text(query)

    if not query:
        return []

    if cache is not None and query in cache:
        return cache[query]

    limit = _normalise_limit(limit)

    try:
        evidence = _search_provider(search_gnews, query, limit, diagnostics)
    except httpx.HTTPError as exc:
        logger.warning(
            "GNews request failed while retrieving evidence: %s",
            type(exc).__name__,
        )
        if diagnostics is not None:
            diagnostics["gnews"] = "error"
        evidence = []

    if evidence:
        if diagnostics is not None:
            diagnostics["gnews"] = "results"
        logger.info("Using GNews evidence.")
        if cache is not None:
            cache[query] = evidence
        return evidence

    broadened_query = _broaden_query(query)
    if broadened_query and broadened_query != query:
        logger.info(
            "Original GNews query returned no evidence; retrying with a "
            "broader query."
        )
        try:
            evidence = _search_provider(
                search_gnews,
                broadened_query,
                limit,
                diagnostics,
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "Broader GNews request failed while retrieving evidence: %s",
                type(exc).__name__,
            )
            if diagnostics is not None:
                diagnostics["gnews"] = "error"
            evidence = []

        if evidence:
            if diagnostics is not None:
                diagnostics["gnews"] = "results"
            logger.info("Using GNews evidence from the broader query.")
            if cache is not None:
                cache[query] = evidence
            return evidence

    logger.info("GNews returned no usable evidence; trying GDELT.")
    fallback_query = broadened_query or query
    try:
        evidence = _search_provider(search_gdelt, fallback_query, limit, diagnostics)
    except httpx.HTTPError as exc:
        logger.warning(
            "GDELT request failed while retrieving evidence: %s",
            type(exc).__name__,
        )
        if diagnostics is not None:
            diagnostics["gdelt"] = "error"
        evidence = []

    if evidence:
        if diagnostics is not None:
            diagnostics["gdelt"] = "results"
        logger.info("Using GDELT fallback evidence.")
        if cache is not None:
            cache[query] = evidence
        return evidence

    logger.warning(
        "No evidence retrieved for the supplied query."
    )

    if cache is not None:
        cache[query] = []
    if diagnostics is not None:
        diagnostics.setdefault("gdelt", "no_results")
        if diagnostics.get("gnews") == "configured":
            diagnostics["gnews"] = "no_results"
    return []