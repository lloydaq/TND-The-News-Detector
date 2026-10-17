from __future__ import annotations

import ipaddress
import json
import logging
import socket
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any, Final, Literal
from urllib.parse import ParseResult, urljoin, urlparse

import httpx
import httpcore
import trafilatura
from bs4 import BeautifulSoup
from bs4.element import NavigableString, TemplateString

logger = logging.getLogger(__name__)


def _redacted_url(url: str) -> str:
    """Keep URL logs useful without recording query parameters or fragments."""
    parsed = urlparse(url)
    return parsed._replace(query="", fragment="").geturl()

DEFAULT_BROWSER_USER_AGENT: Final[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
CRAWLER_FALLBACK_USER_AGENT: Final[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 "
    "(compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)"
)
USER_AGENT: Final[str] = DEFAULT_BROWSER_USER_AGENT
REQUEST_TIMEOUT: Final[float] = 12.0
MAX_REDIRECTS: Final[int] = 5
MIN_ARTICLE_TEXT_LENGTH: Final[int] = 200
MIN_ARTICLE_WORDS: Final[int] = 35
MAX_HTML_BYTES: Final[int] = 2_000_000


class _SafeNetworkBackend(httpcore.SyncBackend):
    """Connect only to addresses that pass the SSRF policy."""

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> httpcore.NetworkStream:
        addresses = _public_addresses(host)
        if not addresses:
            raise httpcore.ConnectError("Host resolved to a blocked address.")

        source_address = None if local_address is None else (local_address, 0)
        last_error: OSError | None = None
        for address in addresses:
            sock = socket.socket(socket.AF_INET6 if ":" in address else socket.AF_INET)
            try:
                if source_address is not None:
                    sock.bind(source_address)
                sock.settimeout(timeout)
                target = (address, port, 0, 0) if ":" in address else (address, port)
                sock.connect(target)
                if socket_options:
                    for option in socket_options:
                        sock.setsockopt(*option)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                return httpcore.SyncStream(sock)
            except OSError as error:
                last_error = error
                sock.close()

        raise httpcore.ConnectError("Unable to connect to the external webpage.") from last_error


def _public_addresses(hostname: str) -> list[str]:
    """Resolve a hostname and return only public IP addresses."""
    try:
        addresses = {
            info[4][0]
            for info in socket.getaddrinfo(
                hostname,
                None,
                type=socket.SOCK_STREAM,
            )
        }
    except socket.gaierror as error:
        raise ArticleFetchError("Unable to fetch the external webpage.") from error

    public: list[str] = []
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            continue
        public.append(address)
    return public

ARTICLE_IGNORE_SELECTORS: Final[list[str]] = [
    "nav",
    "footer",
    "header",
    "aside",
    "script",
    "style",
    "noscript",
    "form",
    "[role='navigation']",
    "[role='banner']",
    "[role='contentinfo']",
    ".nav",
    ".navbar",
    ".navigation",
    ".menu",
    ".footer",
    ".ad",
    ".ads",
    ".advertisement",
    ".cookie",
    ".cookies",
    ".consent",
    ".share",
    ".social",
    ".social-share",
    "[aria-label*='advertisement' i]",
    "[id*='cookie' i]",
    "[class*='cookie' i]",
    "[class*='share' i]",
]

BOILERPLATE_PATTERNS: Final[list[str]] = [
    "all rights reserved",
    "subscribe now",
    "sign up for our newsletter",
    "follow us on",
    "cookie policy",
    "terms of use",
    "terms and conditions",
    "privacy policy",
    "read our privacy policy",
    "manage consent",
]


class ArticleExtractionError(Exception):
    """Base error for URL validation, fetching, or article extraction."""

    failure_status = "ERROR"


class InvalidArticleURL(ArticleExtractionError):
    """The supplied URL is not safe or valid for external fetching."""

    failure_status = "BLOCKED"


class ArticleFetchError(ArticleExtractionError):
    """The external webpage could not be fetched."""

    failure_status = "FETCH_ERROR"

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code
        if status_code == 408:
            self.failure_status = "TIMEOUT"


class ArticleContentError(ArticleExtractionError):
    """The webpage did not contain enough extractable article content."""

    failure_status = "INSUFFICIENT_CONTENT"


@dataclass(frozen=True)
class ExtractedArticle:
    title: str
    text: str
    source: str
    publisher: str
    author: str | None = None
    published_at: str | None = None
    canonical_url: str | None = None
    status: Literal["SUCCESS", "PARTIAL"] = "SUCCESS"
    extraction_method: str = "unknown"
    word_count: int = 0
    warnings: tuple[str, ...] = ()


def extract_article(url: str) -> ExtractedArticle:
    """Fetch and extract an article using a robust multi-level fallback pipeline."""
    parsed_url = _validate_url(url)
    is_msn = _is_msn_domain(parsed_url.hostname)

    # For MSN and aggregator SPA shells, use crawler UA directly to obtain SSR content
    initial_ua = CRAWLER_FALLBACK_USER_AGENT if is_msn else DEFAULT_BROWSER_USER_AGENT
    html = _fetch_html(url, user_agent=initial_ua)

    article, had_metadata = _extract_from_html(html, parsed_url)
    if article:
        return article

    # Fallback to crawler UA if initial browser UA yielded insufficient body
    if initial_ua != CRAWLER_FALLBACK_USER_AGENT:
        try:
            logger.debug(
                "Retrying fetch with crawler-compatible UA for URL: %s",
                _redacted_url(url),
            )
            fallback_html = _fetch_html(url, user_agent=CRAWLER_FALLBACK_USER_AGENT)
            article, had_metadata = _extract_from_html(fallback_html, parsed_url)
            if article:
                return article
        except ArticleExtractionError as e:
            logger.debug("Fallback crawler fetch failed: %s", e)

    if had_metadata:
        logger.warning(
            "Article extraction yielded metadata_only for URL: %s",
            _redacted_url(url),
        )
    logger.error("Article extraction failed for URL: %s", _redacted_url(url))
    raise ArticleContentError("Unable to extract the article content from this URL.")


def _extract_from_html(
    html: str,
    parsed_url: ParseResult,
) -> tuple[ExtractedArticle | None, bool]:
    soup = BeautifulSoup(html, "html.parser")
    html_meta = _extract_html_metadata(soup)
    ld_objects = _find_ld_objects(soup)
    ld_meta = _extract_best_ld_metadata(ld_objects)
    traf_metadata = trafilatura.extract_metadata(html)

    # 1. First attempt: trafilatura
    text = ""
    extraction_method = "failed"
    try:
        raw_traf = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            output_format="txt",
        )
        cleaned_traf = _clean_text(raw_traf)
        if len(cleaned_traf) >= MIN_ARTICLE_TEXT_LENGTH:
            text = cleaned_traf
            extraction_method = "trafilatura"
    except Exception as e:
        logger.debug("Trafilatura extraction encountered an error: %s", e)

    # 2. Second fallback: JSON-LD articleBody
    if len(text) < MIN_ARTICLE_TEXT_LENGTH and ld_meta.get("article_body"):
        cleaned_ld = _clean_text(ld_meta["article_body"])
        if len(cleaned_ld) >= MIN_ARTICLE_TEXT_LENGTH:
            text = cleaned_ld
            extraction_method = "jsonld"

    # 3. Third fallback: <article> element
    if len(text) < MIN_ARTICLE_TEXT_LENGTH:
        cleaned_elem = _extract_article_element(soup)
        if len(cleaned_elem) >= MIN_ARTICLE_TEXT_LENGTH:
            text = cleaned_elem
            extraction_method = "article_element"

    had_metadata = bool(
        html_meta.get("title")
        or ld_meta.get("headline")
        or (traf_metadata and traf_metadata.title)
    )

    if len(text) < MIN_ARTICLE_TEXT_LENGTH:
        return None, had_metadata

    logger.info("Article extraction succeeded using method: %s", extraction_method)

    # Resolve Title
    title = (
        ld_meta.get("headline")
        or _clean_value(traf_metadata.title if traf_metadata else None)
        or html_meta.get("title")
        or "Untitled Article"
    )

    # Resolve Author
    author = (
        ld_meta.get("author")
        or _clean_value(traf_metadata.author if traf_metadata else None)
        or html_meta.get("author")
    )

    # Resolve Published Time
    published_at = (
        ld_meta.get("date_published")
        or _clean_value(traf_metadata.date if traf_metadata else None)
        or html_meta.get("published_at")
    )

    # Resolve Canonical URL
    canonical_url = (
        html_meta.get("canonical_url")
        or ld_meta.get("url")
        or _clean_value(traf_metadata.url if traf_metadata else None)
    )

    # Resolve Publisher and Source
    publisher = _resolve_publisher(
        hostname=parsed_url.hostname or "",
        jsonld_publisher=ld_meta.get("publisher"),
        og_site_name=html_meta.get("site_name"),
        meta_publisher=html_meta.get("publisher"),
        traf_sitename=_clean_value(traf_metadata.sitename if traf_metadata else None),
    )
    source = _hostname(parsed_url.hostname)

    safe_canonical_url = _safe_metadata_url(
        canonical_url,
        parsed_url,
    )
    warnings: list[str] = []
    word_count = len(text.split())
    if extraction_method == "article_element":
        warnings.append("Used constrained HTML fallback extraction.")
    if word_count < MIN_ARTICLE_WORDS:
        warnings.append("The extracted article is unusually short.")
    if not author:
        warnings.append("Author metadata was not available.")
    if not published_at:
        warnings.append("Publication date metadata was not available.")
    if not safe_canonical_url:
        warnings.append("A safe canonical URL was not available.")

    return (
        ExtractedArticle(
            title=title,
            text=text,
            source=source,
            publisher=publisher,
            author=author,
            published_at=published_at,
            canonical_url=safe_canonical_url,
            status=(
                "PARTIAL"
                if extraction_method == "article_element"
                or word_count < MIN_ARTICLE_WORDS
                else "SUCCESS"
            ),
            extraction_method=extraction_method,
            word_count=word_count,
            warnings=tuple(warnings),
        ),
        had_metadata,
    )


def _validate_url(url: str) -> ParseResult:
    try:
        parsed = urlparse(url)
    except ValueError as error:
        raise InvalidArticleURL("Invalid URL.") from error

    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise InvalidArticleURL("Invalid URL.")
    if parsed.username or parsed.password:
        raise InvalidArticleURL("Invalid URL.")
    try:
        parsed.port
    except ValueError as error:
        raise InvalidArticleURL("Invalid URL.") from error
    _validate_hostname(parsed.hostname)
    return parsed


def _validate_hostname(hostname: str) -> None:
    normalized = hostname.rstrip(".").lower()
    if normalized in {"localhost", "localhost.localdomain"}:
        raise InvalidArticleURL("Invalid URL.")

    if not _public_addresses(normalized):
        raise InvalidArticleURL("Invalid URL.")


def _is_msn_domain(hostname: str | None) -> bool:
    if not hostname:
        return False
    norm = hostname.lower().rstrip(".")
    return norm == "msn.com" or norm.endswith(".msn.com")


def _fetch_html(url: str, user_agent: str | None = None) -> str:
    current_url = url
    ua = user_agent or DEFAULT_BROWSER_USER_AGENT
    try:
        transport = httpx.HTTPTransport(trust_env=False)
        # HTTPTransport does not expose its httpcore backend publicly. Replacing
        # its pool keeps hostname-based HTTP Host/TLS SNI while pinning TCP to
        # the address checked by _SafeNetworkBackend.
        transport._pool = httpcore.ConnectionPool(
            network_backend=_SafeNetworkBackend(),
        )
        with httpx.Client(
            follow_redirects=False,
            timeout=REQUEST_TIMEOUT,
            transport=transport,
            headers={
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        ) as client:
            for _ in range(MAX_REDIRECTS + 1):
                response_context = (
                    client.stream("GET", current_url)
                    if hasattr(client, "stream")
                    else nullcontext(client.get(current_url))
                )
                with response_context as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise ArticleFetchError("Unable to fetch the external webpage.")
                        current_url = urljoin(current_url, location)
                        _validate_url(current_url)
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").lower()
                    if content_type and not (
                        "text/html" in content_type
                        or "application/xhtml+xml" in content_type
                    ):
                        raise ArticleContentError(
                            "The external response is not an HTML document."
                        )
                    content_length = response.headers.get("content-length")
                    if content_length:
                        try:
                            if int(content_length) > MAX_HTML_BYTES:
                                raise ArticleContentError(
                                    "The external response is too large."
                                )
                        except ValueError:
                            pass
                    body = bytearray()
                    chunks = (
                        response.iter_bytes()
                        if hasattr(response, "iter_bytes")
                        else (response.content,)
                    )
                    for chunk in chunks:
                        body.extend(chunk)
                        if len(body) > MAX_HTML_BYTES:
                            raise ArticleContentError(
                                "The external response is too large."
                            )
                    return bytes(body).decode(response.encoding or "utf-8", errors="replace")
    except InvalidArticleURL:
        raise
    except httpx.TimeoutException as error:
        timeout_error = ArticleFetchError("Unable to fetch the external webpage.")
        timeout_error.failure_status = "TIMEOUT"
        raise timeout_error from error
    except httpx.HTTPStatusError as error:
        raise ArticleFetchError(
            "Unable to fetch the external webpage.",
            status_code=error.response.status_code,
        ) from error
    except httpx.RequestError as error:
        raise ArticleFetchError("Unable to fetch the external webpage.") from error

    raise ArticleFetchError("Unable to fetch the external webpage.")


def _find_ld_objects(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Parse JSON-LD script blocks looking for article and webpage objects."""
    results: list[tuple[int, dict[str, Any]]] = []
    target_types = {"newsarticle", "article", "reportagenewsarticle", "webpage"}

    for script in soup.find_all("script", type="application/ld+json"):
        raw_text = script.string or script.get_text() or ""
        raw_text = raw_text.strip()
        if not raw_text:
            continue
        try:
            data = json.loads(raw_text)
        except Exception:
            continue

        items: list[Any] = []
        if isinstance(data, list):
            items.extend(data)
        elif isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                items.extend(data["@graph"])
            items.append(data)

        for item in items:
            if not isinstance(item, dict):
                continue
            raw_type = item.get("@type", "")
            types: list[str] = []
            if isinstance(raw_type, str):
                types = [raw_type]
            elif isinstance(raw_type, list):
                types = [str(t) for t in raw_type if isinstance(t, str)]

            clean_types = {t.split("/")[-1].lower() for t in types}
            if clean_types & target_types:
                priority = 1
                if clean_types & {"newsarticle", "reportagenewsarticle"}:
                    priority = 3
                elif "article" in clean_types:
                    priority = 2
                results.append((priority, item))

    results.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in results]


def _extract_best_ld_metadata(ld_objects: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract metadata from the highest-priority JSON-LD object."""
    if not ld_objects:
        return {}

    for obj in ld_objects:
        meta = _extract_single_ld_metadata(obj)
        if meta.get("headline") or meta.get("article_body"):
            return meta

    return _extract_single_ld_metadata(ld_objects[0])


def _extract_single_ld_metadata(obj: dict[str, Any]) -> dict[str, Any]:
    headline = _clean_value(obj.get("headline") or obj.get("name"))
    description = _clean_value(obj.get("description"))
    url = _clean_value(obj.get("url"))
    date_published = _clean_value(
        obj.get("datePublished") or obj.get("dateCreated")
    )

    # Author resolution from JSON-LD
    author_str = None
    author_val = obj.get("author")
    if isinstance(author_val, str):
        author_str = _clean_value(author_val)
    elif isinstance(author_val, dict):
        author_str = _clean_value(author_val.get("name"))
    elif isinstance(author_val, list):
        authors: list[str] = []
        for a in author_val:
            if isinstance(a, str):
                v = _clean_value(a)
                if v:
                    authors.append(v)
            elif isinstance(a, dict):
                v = _clean_value(a.get("name"))
                if v:
                    authors.append(v)
        if authors:
            author_str = ", ".join(authors)

    # Publisher resolution from JSON-LD
    publisher_str = None
    publisher_val = obj.get("publisher")
    if isinstance(publisher_val, str):
        publisher_str = _clean_value(publisher_val)
    elif isinstance(publisher_val, dict):
        publisher_str = _clean_value(publisher_val.get("name"))
    elif isinstance(publisher_val, list):
        for p in publisher_val:
            if isinstance(p, dict):
                v = _clean_value(p.get("name"))
                if v:
                    publisher_str = v
                    break
            elif isinstance(p, str):
                v = _clean_value(p)
                if v:
                    publisher_str = v
                    break

    # articleBody resolution from JSON-LD
    raw_body = obj.get("articleBody") or obj.get("text")
    article_body = ""
    if raw_body and isinstance(raw_body, str):
        if "<" in raw_body and ">" in raw_body:
            body_soup = BeautifulSoup(raw_body, "html.parser")
            paras = [
                p.get_text(" ", strip=True)
                for p in body_soup.find_all(["p", "div"])
                if p.get_text(" ", strip=True)
            ]
            if paras:
                article_body = _clean_paragraph_list(paras)
            else:
                article_body = _clean_text(body_soup.get_text("\n\n", strip=True))
        else:
            article_body = _clean_text(raw_body)

    return {
        "headline": headline,
        "description": description,
        "url": url,
        "date_published": date_published,
        "author": author_str,
        "publisher": publisher_str,
        "article_body": article_body,
    }


def _extract_article_element(soup: BeautifulSoup) -> str:
    """Extract paragraphs from <article> or <main> container."""
    articles = soup.find_all("article")
    if not articles:
        main = soup.find(["main", "div"], attrs={"role": "main"})
        if main:
            articles = [main]

    for article in articles:
        container = BeautifulSoup(str(article), "html.parser")
        for selector in ARTICLE_IGNORE_SELECTORS:
            try:
                for el in container.select(selector):
                    el.decompose()
            except Exception:
                pass

        paragraphs: list[str] = []
        for el in container.find_all(["p", "h2", "h3", "h4"]):
            text = el.get_text(
                " ",
                strip=True,
                types=(NavigableString, TemplateString),
            )
            if not text:
                continue
            if _is_boilerplate_paragraph(text):
                continue
            if el.name == "p" and len(text.split()) < 3:
                continue
            paragraphs.append(text)

        cleaned = _clean_paragraph_list(paragraphs)
        if len(cleaned) >= MIN_ARTICLE_TEXT_LENGTH:
            return cleaned

    return ""


def _extract_html_metadata(soup: BeautifulSoup) -> dict[str, str | None]:
    """Extract metadata from OpenGraph, Twitter, and standard HTML meta tags."""
    def meta_content(*, prop: str | None = None, name: str | None = None) -> str | None:
        attrs = {"property": prop} if prop else {"name": name}
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            return _clean_value(tag.get("content"))
        return None

    og_title = meta_content(prop="og:title")
    meta_title = meta_content(name="title")
    page_title = None
    if soup.title:
        page_title = _clean_value(
            soup.title.get_text(
                " ",
                strip=True,
                types=(NavigableString, TemplateString),
            )
        )

    og_description = meta_content(prop="og:description")
    meta_description = meta_content(name="description")

    og_site_name = meta_content(prop="og:site_name")
    meta_publisher = meta_content(name="publisher") or meta_content(name="dc.publisher")

    og_url = meta_content(prop="og:url")
    canonical_tag = soup.find(
        "link",
        rel=lambda r: r and "canonical" in (r if isinstance(r, list) else [r]),
    )
    canonical_url = _clean_value(canonical_tag.get("href")) if canonical_tag else None

    published_time = (
        meta_content(prop="article:published_time")
        or meta_content(name="article:published_time")
        or meta_content(name="publication_date")
        or meta_content(name="date")
    )

    author = (
        meta_content(name="author")
        or meta_content(prop="author")
        or meta_content(prop="article:author")
        or meta_content(name="dc.creator")
        or meta_content(name="byl")
    )

    return {
        "title": og_title or meta_title or page_title,
        "description": og_description or meta_description,
        "site_name": og_site_name,
        "publisher": meta_publisher,
        "canonical_url": canonical_url or og_url,
        "published_at": published_time,
        "author": author,
    }


def _resolve_publisher(
    hostname: str,
    jsonld_publisher: str | None,
    og_site_name: str | None,
    meta_publisher: str | None,
    traf_sitename: str | None = None,
) -> str:
    """Resolve publisher name while avoiding mislabeling aggregator as publisher."""
    is_msn = _is_msn_domain(hostname)

    # 1. Prefer JSON-LD publisher.name
    if jsonld_publisher:
        if is_msn:
            if jsonld_publisher.lower() != "msn":
                return jsonld_publisher
        else:
            return jsonld_publisher

    # 2. Prefer trafilatura sitename if distinct from aggregator
    if traf_sitename:
        if is_msn:
            if traf_sitename.lower() != "msn":
                return traf_sitename
        else:
            return traf_sitename

    # 3. Check explicit HTML meta publisher
    if meta_publisher:
        if is_msn:
            if meta_publisher.lower() != "msn":
                return meta_publisher
        else:
            return meta_publisher

    # 4. Use og:site_name
    if og_site_name:
        if not (is_msn and og_site_name.lower() == "msn"):
            return og_site_name

    # 5. Fallback to any detected publisher name
    if jsonld_publisher:
        return jsonld_publisher
    if og_site_name:
        return og_site_name

    # 6. Fallback to hostname without www.
    return _hostname(hostname)


def _is_boilerplate_paragraph(text: str) -> bool:
    lower = text.lower()
    words = lower.split()
    return len(words) <= 12 and any(
        lower == pattern
        or lower.startswith(f"{pattern}.")
        or lower.startswith(f"{pattern}:")
        for pattern in BOILERPLATE_PATTERNS
    )


def _safe_metadata_url(
    value: str | None,
    base_url: ParseResult,
) -> str | None:
    """Keep canonical metadata only when it passes the URL policy."""
    if not value:
        return None
    candidate = urljoin(base_url.geturl(), value)
    try:
        _validate_url(candidate)
    except ArticleExtractionError:
        return None
    return candidate


def _clean_paragraph_list(paragraphs: list[str]) -> str:
    """Normalize whitespace and deduplicate paragraphs preserving order."""
    seen: set[str] = set()
    unique_paragraphs: list[str] = []
    for p in paragraphs:
        cleaned = " ".join(p.split())
        if not cleaned:
            continue
        key = cleaned.lower()
        if key not in seen:
            seen.add(key)
            unique_paragraphs.append(cleaned)
    return "\n\n".join(unique_paragraphs)


def _clean_text(text: str | None) -> str:
    if not text:
        return ""
    paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
    return _clean_paragraph_list(paragraphs)


def _clean_value(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _hostname(hostname: str | None) -> str:
    return (hostname or "").rstrip(".").removeprefix("www.")
