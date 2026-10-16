import httpx
from urllib.parse import urlparse

from app.services import evidence_content
from app.services import article_extractor
from app.services.article_extractor import (
    ArticleContentError,
    ArticleFetchError,
    ExtractedArticle,
    InvalidArticleURL,
)


EVIDENCE = {
    "source": "Publisher",
    "description": "A headline",
    "url": "https://example.test/article",
}


def _article(text="A" * 300):
    return ExtractedArticle(
        title="A title",
        text=text,
        source="example.test",
        publisher="Publisher",
    )


def test_successful_article_fetch_and_extraction(monkeypatch):
    calls = []

    def fake_extract(url):
        calls.append(url)
        return _article("Readable article content.")

    monkeypatch.setattr(evidence_content, "extract_article", fake_extract)

    result = evidence_content.retrieve_evidence_content([EVIDENCE])

    assert result[0]["contentStatus"] == "FETCHED"
    assert result[0]["_content"] == "Readable article content."
    assert calls == [EVIDENCE["url"]]


def test_empty_or_unreadable_content_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        evidence_content,
        "extract_article",
        lambda url: _article(""),
    )

    result = evidence_content.retrieve_evidence_content([EVIDENCE])

    assert result[0]["contentStatus"] == "UNAVAILABLE"
    assert "_content" not in result[0]


def test_http_failures_are_unavailable(monkeypatch):
    for error in (ArticleFetchError("404"), ArticleFetchError("500")):
        monkeypatch.setattr(
            evidence_content,
            "extract_article",
            lambda url, error=error: (_ for _ in ()).throw(error),
        )
        result = evidence_content.retrieve_evidence_content([EVIDENCE])
        assert result[0]["contentStatus"] == "UNAVAILABLE"


def test_timeout_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        evidence_content,
        "extract_article",
        lambda url: (_ for _ in ()).throw(
            ArticleFetchError("timeout")
        ),
    )

    assert evidence_content.retrieve_evidence_content([EVIDENCE])[0][
        "contentStatus"
    ] == "UNAVAILABLE"


def test_non_html_and_oversized_content_are_unsupported(monkeypatch):
    for message in ("not an HTML document", "response is too large"):
        monkeypatch.setattr(
            evidence_content,
            "extract_article",
            lambda url, message=message: (_ for _ in ()).throw(
                ArticleContentError(message)
            ),
        )
        result = evidence_content.retrieve_evidence_content([EVIDENCE])
        assert result[0]["contentStatus"] == "UNSUPPORTED_CONTENT"


def test_invalid_and_private_urls_are_blocked(monkeypatch):
    for url in ("file:///secret", "http://localhost/private", "http://10.0.0.1"):
        item = {**EVIDENCE, "url": url}
        monkeypatch.setattr(
            evidence_content,
            "extract_article",
            lambda value: (_ for _ in ()).throw(InvalidArticleURL("blocked")),
        )
        result = evidence_content.retrieve_evidence_content([item])
        assert result[0]["contentStatus"] == "BLOCKED"


def test_duplicate_urls_are_fetched_once_and_cached(monkeypatch):
    calls = []

    def fake_extract(url):
        calls.append(url)
        return _article()

    monkeypatch.setattr(evidence_content, "extract_article", fake_extract)
    items = [EVIDENCE, {**EVIDENCE, "description": "Same URL"}]
    cache = {}

    result = evidence_content.retrieve_evidence_content(items, cache=cache)

    assert len(result) == 1
    assert calls == [EVIDENCE["url"]]

    second = evidence_content.retrieve_evidence_content(items, cache=cache)
    assert len(second) == 1
    assert calls == [EVIDENCE["url"]]


def test_missing_url_is_preserved_without_fetching(monkeypatch):
    monkeypatch.setattr(
        evidence_content,
        "extract_article",
        lambda url: (_ for _ in ()).throw(
            AssertionError("Should not fetch missing URL")
        ),
    )
    item = {"source": "Publisher", "description": "Headline"}

    result = evidence_content.retrieve_evidence_content([item])

    assert result == [{**item, "contentStatus": "UNAVAILABLE"}]


def test_httpx_response_types_can_be_mapped_by_existing_extractor():
    assert issubclass(httpx.ReadTimeout, httpx.RequestError)


class FakeHttpClient:
    responses = []

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url):
        return self.__class__.responses.pop(0)


def _http_response(content, content_type="text/html", status_code=200, headers=None):
    response_headers = {"content-type": content_type}
    if headers:
        response_headers.update(headers)
    return httpx.Response(
        status_code,
        content=content,
        headers=response_headers,
        request=httpx.Request("GET", "https://example.test/article"),
    )


def test_existing_fetcher_rejects_non_html_and_oversized_responses(monkeypatch):
    monkeypatch.setattr(article_extractor.httpx, "Client", FakeHttpClient)
    for response in (
        _http_response(b"{}", content_type="application/json"),
        _http_response(
            b"small",
            headers={"content-length": str(article_extractor.MAX_HTML_BYTES + 1)},
        ),
    ):
        FakeHttpClient.responses = [response]
        try:
            article_extractor._fetch_html(EVIDENCE["url"])
        except ArticleContentError:
            pass
        else:
            raise AssertionError("Expected content rejection")


def test_existing_fetcher_revalidates_redirect_destinations(monkeypatch):
    monkeypatch.setattr(article_extractor.httpx, "Client", FakeHttpClient)
    FakeHttpClient.responses = [
        _http_response(
            b"",
            headers={"location": "http://localhost/private"},
            status_code=302,
        )
    ]

    try:
        article_extractor._fetch_html(EVIDENCE["url"])
    except InvalidArticleURL:
        pass
    else:
        raise AssertionError("Expected unsafe redirect rejection")


def test_public_address_policy_rejects_ipv4_mapped_private_ipv6():
    addresses = article_extractor._public_addresses

    original = article_extractor.socket.getaddrinfo
    article_extractor.socket.getaddrinfo = lambda *args, **kwargs: [
        (0, 0, 0, "", ("::ffff:127.0.0.1", 0, 0, 0))
    ]
    try:
        assert addresses("attacker.test") == []
    finally:
        article_extractor.socket.getaddrinfo = original


def test_streaming_fetch_rejects_body_after_decoded_limit(monkeypatch):
    class StreamingResponse:
        headers = {"content-type": "text/html"}
        encoding = "utf-8"
        is_redirect = False

        def raise_for_status(self):
            pass

        def iter_bytes(self):
            yield b"x" * article_extractor.MAX_HTML_BYTES
            yield b"x"

    class StreamingContext:
        def __enter__(self):
            return StreamingResponse()

        def __exit__(self, *args):
            return False

    class StreamingClient(FakeHttpClient):
        def stream(self, method, url):
            return StreamingContext()

    monkeypatch.setattr(article_extractor.httpx, "Client", StreamingClient)

    try:
        article_extractor._fetch_html(EVIDENCE["url"])
    except ArticleContentError as error:
        assert "too large" in str(error)
    else:
        raise AssertionError("Expected streaming response rejection")


def test_metadata_only_page_is_rejected(monkeypatch):
    monkeypatch.setattr(article_extractor.trafilatura, "extract", lambda *args, **kwargs: "")
    monkeypatch.setattr(
        article_extractor.trafilatura,
        "extract_metadata",
        lambda *args, **kwargs: None,
    )
    html = "<html><head><title>Only a headline</title></head><body><h1>Only a headline</h1></body></html>"

    article, had_metadata = article_extractor._extract_from_html(
        html,
        urlparse("https://example.test/story"),
    )

    assert article is None
    assert had_metadata is True


def test_jsonld_article_body_and_metadata_are_extracted(monkeypatch):
    monkeypatch.setattr(article_extractor.trafilatura, "extract", lambda *args, **kwargs: "")
    monkeypatch.setattr(
        article_extractor.trafilatura,
        "extract_metadata",
        lambda *args, **kwargs: None,
    )
    body = " ".join(f"Sentence {index} contains useful reporting." for index in range(8))
    html = f"""
    <script type="application/ld+json">
    {{
      "@type": "NewsArticle",
      "headline": "A reported story",
      "author": {{"name": "Reporter"}},
      "datePublished": "2025-01-01",
      "publisher": {{"name": "Example News"}},
      "articleBody": "{body}",
      "url": "https://example.test/story"
    }}
    </script>
    """

    article, _ = article_extractor._extract_from_html(
        html,
        urlparse("https://example.test/story"),
    )

    assert article is not None
    assert article.extraction_method == "jsonld"
    assert article.title == "A reported story"
    assert article.publisher == "Example News"
    assert article.author == "Reporter"
    assert article.published_at == "2025-01-01"
    assert article.status == "SUCCESS"


def test_duplicate_fallback_paragraphs_are_removed(monkeypatch):
    monkeypatch.setattr(article_extractor.trafilatura, "extract", lambda *args, **kwargs: "")
    monkeypatch.setattr(
        article_extractor.trafilatura,
        "extract_metadata",
        lambda *args, **kwargs: None,
    )
    paragraph = (
        "This is a substantial reported paragraph with enough words to be useful "
        "and to provide context for readers following the story."
    )
    second_paragraph = (
        "The second reported paragraph adds independent context and relevant details "
        "about the event, its timing, and the people involved."
    )
    html = (
        "<article>"
        + "".join(
            f"<p>{value}</p>"
            for value in (paragraph, second_paragraph, paragraph, second_paragraph)
        )
        + "</article>"
    )

    article, _ = article_extractor._extract_from_html(
        html,
        urlparse("https://example.test/story"),
    )

    assert article is not None
    assert article.extraction_method == "article_element"
    assert article.text.count(paragraph) == 1
    assert article.status == "PARTIAL"


def test_unsafe_canonical_metadata_is_discarded_without_fetching(monkeypatch):
    monkeypatch.setattr(
        article_extractor.trafilatura,
        "extract",
        lambda *args, **kwargs: " ".join(
            f"Reported sentence {index}." for index in range(40)
        ),
    )
    monkeypatch.setattr(
        article_extractor.trafilatura,
        "extract_metadata",
        lambda *args, **kwargs: None,
    )
    html = (
        '<link rel="canonical" href="http://127.0.0.1/private">'
        "<title>Reported story</title>"
    )

    article, _ = article_extractor._extract_from_html(
        html,
        urlparse("https://example.test/story"),
    )

    assert article is not None
    assert article.canonical_url is None
    assert "A safe canonical URL was not available." in article.warnings


def test_http_status_is_preserved_for_fetch_failures(monkeypatch):
    response = _http_response(b"forbidden", status_code=403)
    monkeypatch.setattr(article_extractor.httpx, "Client", FakeHttpClient)
    FakeHttpClient.responses = [response]

    try:
        article_extractor._fetch_html(EVIDENCE["url"])
    except ArticleFetchError as error:
        assert error.status_code == 403
        assert error.failure_status == "FETCH_ERROR"
    else:
        raise AssertionError("Expected fetch failure")
