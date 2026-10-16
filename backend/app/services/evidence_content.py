import logging
from typing import Any, Literal

from app.services.article_extractor import (
    ArticleContentError,
    ArticleFetchError,
    InvalidArticleURL,
    extract_article,
)

logger = logging.getLogger(__name__)

ContentStatus = Literal[
    "FETCHED",
    "UNAVAILABLE",
    "BLOCKED",
    "UNSUPPORTED_CONTENT",
]
MAX_ARTICLES = 3


def _clean(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def retrieve_evidence_content(
    evidence: list[dict[str, Any]],
    cache: dict[str, dict[str, Any]] | None = None,
    max_articles: int = MAX_ARTICLES,
) -> list[dict[str, Any]]:
    """Attach extracted article text for internal verification only."""

    cache = cache if cache is not None else {}
    enriched: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for item in evidence[:max_articles]:
        if not isinstance(item, dict):
            continue

        result = dict(item)
        url = _clean(item.get("url"))
        if not url or url in seen_urls:
            if not url:
                result["contentStatus"] = "UNAVAILABLE"
                enriched.append(result)
            continue
        seen_urls.add(url)

        if url in cache:
            result.update(cache[url])
            enriched.append(result)
            continue

        try:
            article = extract_article(url)
        except InvalidArticleURL:
            content_result = {"contentStatus": "BLOCKED"}
        except ArticleContentError as exc:
            message = str(exc).lower()
            status = (
                "UNSUPPORTED_CONTENT"
                if "not an html document" in message
                or "too large" in message
                else "UNAVAILABLE"
            )
            content_result = {"contentStatus": status}
        except ArticleFetchError:
            content_result = {"contentStatus": "UNAVAILABLE"}
        except Exception as exc:
            logger.warning(
                "Unexpected article content retrieval failure: %s",
                type(exc).__name__,
            )
            content_result = {"contentStatus": "UNAVAILABLE"}
        else:
            content = _clean(article.text)
            if not content:
                content_result = {"contentStatus": "UNAVAILABLE"}
            else:
                source_quality = result.get("sourceQuality")
                if isinstance(source_quality, dict):
                    source_quality = dict(source_quality)
                    source_quality["contentAvailable"] = True
                content_result = {
                    "contentStatus": "FETCHED",
                    "evidenceType": "ARTICLE_TEXT",
                    "_content": content,
                }
                if source_quality is not None:
                    content_result["sourceQuality"] = source_quality

        cache[url] = content_result
        result.update(content_result)
        enriched.append(result)

    return enriched
