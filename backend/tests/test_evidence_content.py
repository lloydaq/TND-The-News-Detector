import httpx

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
