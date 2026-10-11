import httpx

from app.services import evidence_retriever


def _response(payload, status_code=200):
    return httpx.Response(
        status_code,
        json=payload,
        request=httpx.Request("GET", "https://provider.test/search"),
    )


class FakeClient:
    responses = []
    queries = []

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, params=None, **kwargs):
        self.__class__.queries.append(
            params["q"] if "q" in params else params["query"]
        )
        return self.__class__.responses.pop(0)


def test_exact_gnews_query_returns_results(monkeypatch):
    FakeClient.responses = [
        _response(
            {
                "articles": [
                    {
                        "title": "ISRO announces satellite mission",
                        "url": "https://example.test/article",
                        "source": {"name": "Example News"},
                    }
                ]
            }
        )
    ]
    FakeClient.queries = []
    monkeypatch.setattr(evidence_retriever.httpx, "Client", FakeClient)
    monkeypatch.setenv("GNEWS_API_KEY", "test-key")

    result = evidence_retriever.search_evidence(
        "ISRO announced a new satellite mission",
        limit=3,
    )

    assert result == [
        {
            "source": "Example News",
            "description": "ISRO announces satellite mission",
            "url": "https://example.test/article",
        }
    ]
    assert FakeClient.queries == ["ISRO announced a new satellite mission"]


def test_broader_gnews_query_is_used_when_exact_query_fails(monkeypatch):
    FakeClient.responses = [
        _response({"articles": []}),
        _response(
            {
                "articles": [
                    {
                        "title": "ISRO satellite mission succeeds",
                        "url": "https://example.test/isro",
                        "source": {"name": "Example News"},
                    }
                ]
            }
        ),
    ]
    FakeClient.queries = []
    monkeypatch.setattr(evidence_retriever.httpx, "Client", FakeClient)
    monkeypatch.setenv("GNEWS_API_KEY", "test-key")

    result = evidence_retriever.search_evidence(
        "ISRO announced a new satellite mission",
    )

    assert len(result) == 1
    assert FakeClient.queries == [
        "ISRO announced a new satellite mission",
        "ISRO satellite mission",
    ]


def test_gdelt_is_used_after_both_gnews_queries_fail(monkeypatch):
    FakeClient.responses = [
        _response({"articles": []}),
        _response({"articles": []}),
        _response(
            {
                "articles": [
                    {
                        "title": "ISRO mission report",
                        "url": "https://example.test/gdelt",
                        "domain": "example.test",
                    }
                ]
            }
        ),
    ]
    FakeClient.queries = []
    monkeypatch.setattr(evidence_retriever.httpx, "Client", FakeClient)
    monkeypatch.setenv("GNEWS_API_KEY", "test-key")

    result = evidence_retriever.search_evidence(
        "ISRO announced a new satellite mission",
    )

    assert result[0]["source"] == "example.test"
    assert FakeClient.queries == [
        "ISRO announced a new satellite mission",
        "ISRO satellite mission",
        "ISRO satellite mission",
    ]


def test_no_provider_results_returns_empty_list(monkeypatch):
    monkeypatch.setattr(evidence_retriever, "search_gnews", lambda *args: [])
    monkeypatch.setattr(evidence_retriever, "search_gdelt", lambda *args: [])

    assert evidence_retriever.search_evidence("ISRO satellite mission") == []


def test_provider_errors_do_not_escape(monkeypatch):
    monkeypatch.setattr(
        evidence_retriever,
        "search_gnews",
        lambda *args: (_ for _ in ()).throw(httpx.ReadTimeout("timed out")),
    )
    monkeypatch.setattr(
        evidence_retriever,
        "search_gdelt",
        lambda *args: (_ for _ in ()).throw(httpx.HTTPError("provider failed")),
    )

    assert evidence_retriever.search_evidence("ISRO satellite mission") == []


def test_invalid_json_is_ignored(monkeypatch):
    class InvalidJsonResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            raise ValueError("invalid JSON")

    FakeClient.responses = [InvalidJsonResponse()]
    FakeClient.queries = []
    monkeypatch.setattr(evidence_retriever.httpx, "Client", FakeClient)
    monkeypatch.setenv("GNEWS_API_KEY", "test-key")

    assert evidence_retriever.search_gnews("ISRO mission") == []


def test_http_error_is_ignored_for_both_providers(monkeypatch):
    FakeClient.responses = [_response({"error": "bad key"}, status_code=401)]
    monkeypatch.setattr(evidence_retriever.httpx, "Client", FakeClient)
    monkeypatch.setenv("GNEWS_API_KEY", "test-key")

    assert evidence_retriever.search_gnews("ISRO mission") == []

    FakeClient.responses = [_response({"error": "unavailable"}, status_code=503)]
    assert evidence_retriever.search_gdelt("ISRO mission") == []


def test_malformed_articles_field_is_ignored(monkeypatch):
    FakeClient.responses = [_response({"articles": {"title": "not a list"}})]
    monkeypatch.setattr(evidence_retriever.httpx, "Client", FakeClient)
    monkeypatch.setenv("GNEWS_API_KEY", "test-key")

    assert evidence_retriever.search_gnews("ISRO mission") == []


def test_missing_api_key_skips_gnews(monkeypatch):
    monkeypatch.delenv("GNEWS_API_KEY", raising=False)
    monkeypatch.setattr(
        evidence_retriever.httpx,
        "Client",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("GNews should not be called")
        ),
    )

    assert evidence_retriever.search_gnews("ISRO mission") == []


def test_missing_title_or_url_is_not_returned(monkeypatch):
    FakeClient.responses = [
        _response(
            {
                "articles": [
                    {"title": "Missing URL"},
                    {"url": "https://example.test/no-title"},
                    {
                        "title": "Usable",
                        "url": "https://example.test/usable",
                        "source": {"name": "Publisher"},
                    },
                ]
            }
        )
    ]
    monkeypatch.setattr(evidence_retriever.httpx, "Client", FakeClient)
    monkeypatch.setenv("GNEWS_API_KEY", "test-key")

    assert evidence_retriever.search_gnews("ISRO mission") == [
        {
            "source": "Publisher",
            "description": "Usable",
            "url": "https://example.test/usable",
        }
    ]


def test_gnews_http_400_syntax_error_handled_gracefully(monkeypatch):
    FakeClient.responses = [
        _response({"errors": {"q": "syntax error"}}, status_code=400)
    ]
    FakeClient.queries = []
    monkeypatch.setattr(evidence_retriever.httpx, "Client", FakeClient)
    monkeypatch.setenv("GNEWS_API_KEY", "test-key")

    result = evidence_retriever.search_gnews("malformed'query")
    assert result == []


def test_gnews_query_sanitization_removes_problematic_characters():
    from app.services.evidence_retriever import _sanitize_gnews_query

    # Possessives and hyphens
    assert _sanitize_gnews_query("Moon's south pole") == "Moon south pole"
    assert _sanitize_gnews_query("COVID-19 vaccine") == "COVID 19 vaccine"
    assert _sanitize_gnews_query("Chandrayaan-3") == "Chandrayaan 3"
    # Punctuation
    assert _sanitize_gnews_query("NASA confirmed: water exists?") == "NASA confirmed water exists"


def test_gdelt_http_429_handled_gracefully(monkeypatch):
    FakeClient.responses = [
        httpx.Response(
            429,
            headers={"Retry-After": "10"},
            request=httpx.Request("GET", "https://api.gdeltproject.org"),
        )
    ]
    FakeClient.queries = []
    monkeypatch.setattr(evidence_retriever.httpx, "Client", FakeClient)

    result = evidence_retriever.search_gdelt("Moon water ice")
    assert result == []


def test_provider_deduplication_by_canonical_url(monkeypatch):
    FakeClient.responses = [
        _response(
            {
                "articles": [
                    {
                        "title": "Article 1",
                        "url": "https://example.test/story/",
                        "source": {"name": "Source A"},
                    },
                    {
                        "title": "Article 1 Duplicate",
                        "url": "https://example.test/story",
                        "source": {"name": "Source B"},
                    },
                    {
                        "title": "Article 2",
                        "url": "https://example.test/other",
                        "source": {"name": "Source C"},
                    },
                ]
            }
        )
    ]
    monkeypatch.setattr(evidence_retriever.httpx, "Client", FakeClient)
    monkeypatch.setenv("GNEWS_API_KEY", "test-key")

    results = evidence_retriever.search_gnews("mission", limit=5)
    assert len(results) == 2
    assert results[0]["description"] == "Article 1"
    assert results[1]["description"] == "Article 2"


def test_one_provider_failing_while_another_succeeds(monkeypatch):
    # GNews fails with 400, GDELT succeeds
    FakeClient.responses = [
        _response({"error": "Bad Request"}, status_code=400),
        _response(
            {
                "articles": [
                    {
                        "title": "GDELT success article",
                        "url": "https://gdelt.test/news",
                        "domain": "gdelt.test",
                    }
                ]
            }
        ),
    ]
    FakeClient.queries = []
    monkeypatch.setattr(evidence_retriever.httpx, "Client", FakeClient)
    monkeypatch.setenv("GNEWS_API_KEY", "test-key")

    result = evidence_retriever.search_evidence("Moon exploration")
    assert len(result) == 1
    assert result[0]["source"] == "gdelt.test"
    assert result[0]["description"] == "GDELT success article"


def test_invalid_url_schemes_are_rejected():
    from app.services.evidence_retriever import _normalise_article

    assert _normalise_article("Title", "ftp://example.test", "Source") is None
    assert _normalise_article("Title", "file:///etc/passwd", "Source") is None
    assert _normalise_article("Title", "javascript:alert(1)", "Source") is None
    assert _normalise_article("Title", "", "Source") is None
    valid = _normalise_article("Title", "https://example.test/valid", "Source")
    assert valid is not None
    assert valid["url"] == "https://example.test/valid"

