import logging
import os
import re
import inspect
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

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

EvidenceItem = dict[str, Any]


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
        parsed = urlparse(clean)
        scheme = parsed.scheme.lower()
        hostname = (parsed.hostname or "").lower()
        if not hostname or parsed.username or parsed.password:
            return ""
        port = parsed.port
        netloc = hostname
        if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
            netloc = f"{hostname}:{port}"
        query = urlencode(
            sorted(
                (key, value)
                for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                if not key.lower().startswith("utm_")
                and key.lower() not in {"fbclid", "gclid"}
            )
        )
        return urlunparse((scheme, netloc, parsed.path.rstrip("/"), "", query, ""))
    except ValueError:
        return clean


def _sanitize_gnews_query(query: str) -> str:
    """Sanitize query for GNews search syntax.

    Removes possessives, hyphens, and punctuation that cause GNews
    HTTP 400 syntax errors while preserving alphanumeric search keywords.
    """
    clean = re.sub(r"['’]s\b", "", query)
    clean = re.sub(r"[^A-Za-z0-9\s]", " ", clean)
    return " ".join(clean.split())[:200]


def generate_search_queries(claim: Any, max_queries: int = 2) -> list[str]:
    """Create a small deterministic query set without changing the claim."""
    clean = _clean_text(claim)
    if not clean:
        return []
    exact = _sanitize_gnews_query(clean)
    if not exact:
        return []
    queries = [exact]
    fallback = _broaden_query(clean)
    if fallback and fallback != exact and len(queries) < max(1, min(max_queries, 2)):
        queries.append(fallback)
    return queries


def _broaden_query(query: str) -> str:
    """Create one bounded fallback while preserving claim-changing terms."""
    clean = re.sub(r"['’]s\b", "", query)
    tokens = re.findall(r"[A-Za-z0-9]+", clean)
    protected = {
        "not", "no", "never", "may", "might", "could", "if", "unless",
        "because", "rejected", "approved", "denied", "according",
    }
    meaningful = [
        token for token in tokens
        if token.lower() not in _QUERY_FILLER_WORDS
        or token.lower() in protected
        or token[:1].isupper()
        or any(character.isdigit() for character in token)
    ]
    if len(meaningful) > 4:
        entities = [
            token for token in meaningful
            if token[:1].isupper()
            or any(character.isdigit() for character in token)
            or token.lower() in protected
        ]
        remaining = [token for token in meaningful if token not in entities]
        meaningful = entities + remaining[:max(0, 4 - len(entities))]
    return " ".join(meaningful)[:200]


def _normalise_date(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    try:
        if re.fullmatch(r"\d{8}T\d{6}Z", text):
            return datetime.strptime(text, "%Y%m%dT%H%M%SZ").isoformat() + "Z"
        return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return ""


def _quality_indicators(url: str, source: str) -> dict[str, Any]:
    parsed = urlparse(url)
    return {
        "secureTransport": parsed.scheme.lower() == "https",
        "metadataComplete": bool(
            source and source != "News publisher" and parsed.hostname
        ),
        "contentAvailable": False,
        "reputation": "UNKNOWN",
    }



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

    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"https", "http"} or not parsed.hostname:
        return None
    if parsed.username or parsed.password:
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
            if diagnostics is not None:
                diagnostics["gnews"] = "invalid_response"
            logger.warning("GNews returned invalid JSON.")
            return []

        if not isinstance(data, dict):
            if diagnostics is not None:
                diagnostics["gnews"] = "invalid_response"
            logger.warning("GNews returned an unexpected response.")
            return []

        if "articles" not in data:
            if diagnostics is not None:
                diagnostics["gnews"] = "invalid_response"
            logger.warning("GNews response omitted the articles field.")
            return []
        articles = data["articles"]

        if not isinstance(articles, list):
            if diagnostics is not None:
                diagnostics["gnews"] = "invalid_response"
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
                    published_at = _normalise_date(article.get("publishedAt"))
                    if published_at:
                        item["publishedAt"] = published_at
                    evidence.append(item)

            if len(evidence) >= _normalise_limit(limit):
                break

        logger.info(
            "GNews returned %d usable article(s).",
            len(evidence),
        )
        if diagnostics is not None:
            diagnostics["gnews"] = "results" if evidence else "no_results"

        return evidence

    except httpx.HTTPStatusError as exc:
        # Do not log the full request URL because it contains the API key.
        logger.warning(
            "GNews returned HTTP %s.",
            exc.response.status_code,
        )
        if diagnostics is not None:
            diagnostics["gnews"] = (
                "rate_limited" if exc.response.status_code == 429
                else "auth_error" if exc.response.status_code in {401, 403}
                else "quota_exhausted"
                if exc.response.status_code == 402
                else "error"
            )

    except httpx.RequestError as exc:
        logger.warning(
            "GNews network request failed: %s",
            type(exc).__name__,
        )
        if diagnostics is not None:
            diagnostics["gnews"] = (
                "timeout" if isinstance(exc, httpx.TimeoutException)
                else "network_error"
            )

    return []


def search_gdelt(
    query: str,
    limit: int = DEFAULT_LIMIT,
    diagnostics: dict[str, str] | None = None,
) -> list[EvidenceItem]:
    """Search GDELT for related news articles."""

    original_claim = _clean_text(query)
    queries = generate_search_queries(original_claim, max_queries=2)
    if not queries:
        return []
    query = queries[0]

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
            if diagnostics is not None:
                diagnostics["gdelt"] = "invalid_response"
            logger.warning(
                "GDELT returned a non-JSON response (HTTP %s).",
                response.status_code,
            )
            return []

        if not isinstance(data, dict):
            if diagnostics is not None:
                diagnostics["gdelt"] = "invalid_response"
            logger.warning("GDELT returned an unexpected response.")
            return []

        if "articles" not in data:
            if diagnostics is not None:
                diagnostics["gdelt"] = "invalid_response"
            logger.warning("GDELT response omitted the articles field.")
            return []
        articles = data["articles"]

        if not isinstance(articles, list):
            if diagnostics is not None:
                diagnostics["gdelt"] = "invalid_response"
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
                    published_at = _normalise_date(
                        article.get("seendate") or article.get("date")
                    )
                    if published_at:
                        item["publishedAt"] = published_at
                    evidence.append(item)

            if len(evidence) >= _normalise_limit(limit):
                break

        logger.info(
            "GDELT returned %d usable article(s).",
            len(evidence),
        )
        if diagnostics is not None:
            diagnostics["gdelt"] = "results" if evidence else "no_results"

        return evidence

    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            retry_after = exc.response.headers.get("Retry-After")
            logger.warning(
                "GDELT returned HTTP 429 (rate limited). Retry-After: %s",
                retry_after,
            )
            if diagnostics is not None:
                diagnostics["gdelt"] = "rate_limited"
        else:
            logger.warning(
                "GDELT returned HTTP %s.",
                exc.response.status_code,
            )
            if diagnostics is not None:
                diagnostics["gdelt"] = "error"

    except httpx.RequestError as exc:
        logger.warning(
            "GDELT network request failed: %s",
            type(exc).__name__,
        )
        if diagnostics is not None:
            diagnostics["gdelt"] = (
                "timeout" if isinstance(exc, httpx.TimeoutException)
                else "network_error"
            )

    return []


def search_evidence(
    query: str,
    limit: int = DEFAULT_LIMIT,
    cache: dict[str, list[EvidenceItem]] | None = None,
    diagnostics: dict[str, str] | None = None,
) -> list[EvidenceItem]:
    """Search configured providers once with bounded, honest orchestration.

    An empty result is distinct from a provider failure in ``diagnostics``.
    Results from both providers are merged deterministically without treating
    duplicate URLs as independent corroboration.
    """

    original_claim = _clean_text(query)
    queries = generate_search_queries(original_claim, max_queries=2)
    if not queries:
        return []
    query = queries[0]

    if cache is not None and query in cache:
        return cache[query]

    limit = _normalise_limit(limit)

    provider_results: list[EvidenceItem] = []
    for query_index, query in enumerate(queries):
        for provider_name, provider in (
            ("gnews", search_gnews),
            ("gdelt", search_gdelt),
        ):
            try:
                results = _search_provider(provider, query, limit, diagnostics)
            except (httpx.HTTPError, OSError, ValueError) as exc:
                logger.warning(
                    "%s request failed while retrieving evidence: %s",
                    provider_name,
                    type(exc).__name__,
                )
                if diagnostics is not None:
                    diagnostics[provider_name] = "error"
                continue
            for item in results:
                if isinstance(item, dict):
                    item = dict(item)
                    item.setdefault("provider", provider_name)
                    item.setdefault("evidenceType", "HEADLINE_ONLY")
                    item.setdefault(
                        "sourceQuality",
                        _quality_indicators(
                            _clean_text(item.get("url")),
                            _clean_text(item.get("source")),
                        ),
                    )
                    item["query"] = query
                    item["originalClaim"] = original_claim
                    provider_results.append(item)
        if provider_results or query_index + 1 >= 2:
            break

    evidence: list[EvidenceItem] = []
    seen_urls: dict[str, EvidenceItem] = {}
    for item in provider_results:
        url_key = _canonical_url(_clean_text(item.get("url")))
        if url_key and url_key in seen_urls:
            providers = seen_urls[url_key].setdefault("providers", [])
            provider = item.get("provider")
            if provider and provider not in providers:
                providers.append(provider)
            seen_urls[url_key]["independence"] = "UNKNOWN"
            continue
        if url_key:
            item["providers"] = [item.get("provider", "unknown")]
            item["independence"] = "UNKNOWN"
            seen_urls[url_key] = item
        evidence.append(item)
        if len(evidence) >= limit:
            break

    if diagnostics is not None and not provider_results:
        diagnostics.setdefault("gnews", "no_results")
        diagnostics.setdefault("gdelt", "no_results")
    if cache is not None:
        cache[query] = evidence
    return evidence