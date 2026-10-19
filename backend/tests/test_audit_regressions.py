"""Regression tests for defects found in the full-application audit."""

import ipaddress
from contextlib import nullcontext

import pytest
from fastapi.testclient import TestClient

from app.main import MAX_REQUEST_BODY_BYTES, app
from app.models.schemas import AnalyzeRequest
from app.services import analyzer, article_extractor, evidence_content, evidence_verifier
from app.services.article_extractor import ArticleFetchError
from app.services.evidence_verifier import VerificationResult

ORIGIN = "http://127.0.0.1:5500"


@pytest.fixture
def client():
    return TestClient(app)


# --- SSRF address policy -------------------------------------------------


@pytest.mark.parametrize(
    "address",
    [
        "100.64.0.1",  # carrier-grade NAT shared space
        "100.100.100.200",  # Alibaba Cloud metadata service
        "169.254.169.254",  # link-local cloud metadata
        "127.0.0.1",
        "10.0.0.1",
        "192.0.0.8",
        "198.18.0.1",
        "::1",
        "fd00::1",
        "::ffff:127.0.0.1",
        "::ffff:100.64.0.1",
        "64:ff9b::7f00:1",  # NAT64 wrapping 127.0.0.1
        "64:ff9b::a00:1",  # NAT64 wrapping 10.0.0.1
        "ff0e::1",  # global-scope multicast
    ],
)
def test_non_public_addresses_are_blocked(address):
    assert not article_extractor._is_public_ip(ipaddress.ip_address(address))


@pytest.mark.parametrize(
    "address",
    ["93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946", "64:ff9b::5db8:d822"],
)
def test_public_addresses_are_allowed(address):
    assert article_extractor._is_public_ip(ipaddress.ip_address(address))


def test_hostname_resolving_to_shared_address_space_is_rejected(monkeypatch):
    monkeypatch.setattr(
        article_extractor.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, "", ("100.100.100.200", 0))],
    )
    with pytest.raises(article_extractor.InvalidArticleURL):
        article_extractor._validate_url("http://metadata.example.test/latest")


# --- Total fetch deadline ------------------------------------------------


def test_slow_drip_response_hits_total_fetch_deadline(monkeypatch):
    clock = {"now": 0.0}

    class DripResponse:
        is_redirect = False
        headers = {"content-type": "text/html"}
        encoding = "utf-8"

        def raise_for_status(self):
            return None

        def iter_bytes(self):
            for _ in range(10):
                clock["now"] += article_extractor.MAX_FETCH_SECONDS / 2 + 1
                yield b"<p>slow</p>"

    class DripClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def stream(self, method, url):
            return nullcontext(DripResponse())

    monkeypatch.setattr(article_extractor.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(article_extractor.httpx, "Client", DripClient)

    with pytest.raises(ArticleFetchError) as error:
        article_extractor._fetch_html("https://news.example.test/story")
    assert error.value.failure_status == "TIMEOUT"


# --- Malformed model output must not crash analysis ----------------------


def _stub_pipeline(monkeypatch, model_output):
    monkeypatch.setattr(analyzer, "request_json", lambda *args, **kwargs: model_output)
    monkeypatch.setattr(analyzer, "search_evidence", lambda claim_text, limit: [])
    monkeypatch.setattr(
        analyzer,
        "retrieve_evidence_content",
        lambda evidence, cache, max_articles: evidence,
    )
    monkeypatch.setattr(
        analyzer,
        "verify_evidence",
        lambda claim, evidence, max_articles: VerificationResult(
            evidence=[], verificationStatus="INSUFFICIENT_EVIDENCE"
        ),
    )


@pytest.mark.parametrize(
    "model_output",
    [
        {"sourceReliability": ["High"], "signals": [], "claims": []},
        {"sourceReliability": {"v": 1}, "signals": [], "claims": []},
        {
            "sourceReliability": "High",
            "signals": [{"name": "Tone", "status": {"bad": 1}}],
            "claims": [],
        },
        {
            "sourceReliability": "High",
            "signals": [{"name": ["Tone"], "status": ["warning"]}],
            "claims": [],
        },
    ],
)
def test_unhashable_model_fields_degrade_instead_of_crashing(monkeypatch, model_output):
    _stub_pipeline(monkeypatch, model_output)

    response = analyzer.analyze_content(
        AnalyzeRequest(type="text", content="The council approved the budget.")
    )

    assert response.source_reliability in {"Unknown", "High"}
    assert all(signal.status in {"positive", "warning", "unknown"} for signal in response.signals)
    assert all(isinstance(signal.name, str) and signal.name for signal in response.signals)
    if isinstance(model_output["sourceReliability"], str):
        assert response.analysis_status == "DEGRADED"
    else:
        assert response.source_reliability == "Unknown"


def test_verifier_ignores_unhashable_article_index(monkeypatch):
    monkeypatch.setattr(
        evidence_verifier,
        "request_json",
        lambda *args, **kwargs: {
            "assessments": [
                {"articleIndex": [1], "relevance": "SUPPORTS", "explanation": "x"},
                {"articleIndex": {"i": 1}, "relevance": "SUPPORTS"},
            ]
        },
    )

    result = evidence_verifier.verify_evidence(
        "The council approved the budget.",
        [
            {
                "source": "Publisher",
                "description": "Council approves budget",
                "url": "https://example.test/budget",
            }
        ],
    )

    assert result.verification_status == "UNVERIFIABLE"
    assert result.degraded is True
    assert all(item.relevance != "SUPPORTS" for item in result.evidence)


def test_pasted_text_never_receives_a_model_invented_source_rating(monkeypatch):
    _stub_pipeline(
        monkeypatch, {"sourceReliability": "Moderate", "signals": [], "claims": []}
    )

    response = analyzer.analyze_content(
        AnalyzeRequest(type="text", content="The council approved the budget.")
    )

    assert response.source_reliability == "Unknown"


# --- Content truncation is disclosed -------------------------------------


def test_text_beyond_prompt_limit_is_reported_as_partial(monkeypatch):
    captured = {}

    def fake_request_json(httpx_module, url, payload, timeout):
        captured["prompt"] = payload["prompt"]
        return {"sourceReliability": "Unknown", "signals": [], "claims": []}

    _stub_pipeline(monkeypatch, None)
    monkeypatch.setattr(analyzer, "request_json", fake_request_json)
    limit = analyzer.MAX_PROMPT_CONTENT_CHARS
    content = "a" * limit + "TAIL_MARKER"

    response = analyzer.analyze_content(AnalyzeRequest(type="text", content=content))

    assert "TAIL_MARKER" not in captured["prompt"]
    assert response.analysis_status == "DEGRADED"
    assert f"Only the first {limit:,} characters of the content were analyzed" in (
        response.degradation_reasons
    )


def test_text_within_prompt_limit_is_not_flagged(monkeypatch):
    _stub_pipeline(
        monkeypatch, {"sourceReliability": "Unknown", "signals": [], "claims": []}
    )

    response = analyzer.analyze_content(
        AnalyzeRequest(type="text", content="a" * analyzer.MAX_PROMPT_CONTENT_CHARS)
    )

    assert response.analysis_status == "COMPLETE"


# --- Evidence content respects the analysis deadline ---------------------


def test_evidence_content_is_not_fetched_after_deadline(monkeypatch):
    calls = []
    monkeypatch.setattr(
        evidence_content, "extract_article", lambda url: calls.append(url)
    )
    cache = {}

    result = evidence_content.retrieve_evidence_content(
        [{"source": "P", "description": "H", "url": "https://example.test/a"}],
        cache=cache,
        deadline=evidence_content.time.monotonic() - 1,
    )

    assert calls == []
    assert result[0]["contentStatus"] == "UNAVAILABLE"
    assert cache == {}


def test_analyzer_passes_its_deadline_to_content_retrieval(monkeypatch):
    received = {}

    def fake_retrieve(evidence, cache, max_articles, deadline):
        received["deadline"] = deadline
        return evidence

    _stub_pipeline(
        monkeypatch,
        {
            "sourceReliability": "Unknown",
            "signals": [],
            "claims": [{"id": 1, "text": "The council approved the budget."}],
        },
    )
    monkeypatch.setattr(analyzer, "retrieve_evidence_content", fake_retrieve)
    before = analyzer.time.monotonic()

    analyzer.analyze_content(AnalyzeRequest(type="text", content="Budget news."))

    assert before < received["deadline"] <= analyzer.time.monotonic() + analyzer.MAX_ANALYSIS_SECONDS


# --- API error responses -------------------------------------------------


def test_unexpected_exception_returns_json_500_with_cors(client, monkeypatch):
    def boom(request, article=None):
        raise TypeError("unhashable type: 'list'")

    monkeypatch.setattr("app.routes.analysis.analyze_content", boom)

    response = client.post(
        "/api/analyze",
        json={"type": "text", "content": "Some article text."},
        headers={"Origin": ORIGIN},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "The analysis failed unexpectedly. Please try again."}
    assert "unhashable" not in response.text
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_unexpected_exception_releases_concurrency_slot(client, monkeypatch):
    def boom(request, article=None):
        raise TypeError("boom")

    monkeypatch.setattr("app.routes.analysis.analyze_content", boom)
    for _ in range(5):
        response = client.post(
            "/api/analyze", json={"type": "text", "content": "Some article text."}
        )
        assert response.status_code == 500


def test_oversized_body_413_carries_cors_headers(client):
    response = client.post(
        "/api/analyze",
        content=b"x" * (MAX_REQUEST_BODY_BYTES + 1),
        headers={"content-type": "application/json", "Origin": ORIGIN},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body is too large."}
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_too_long_content_422_is_readable_and_does_not_echo_input(client):
    response = client.post(
        "/api/analyze",
        json={"type": "text", "content": "ECHO" * 25_001},
        headers={"Origin": ORIGIN},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Content must be at most 100,000 characters."}
    assert "ECHO" not in response.text
    assert response.headers["access-control-allow-origin"] == ORIGIN


@pytest.mark.parametrize(
    ("kwargs", "detail"),
    [
        ({"content": b"{bad", "headers": {"content-type": "application/json"}}, "The request body is not valid JSON."),
        ({"json": {"type": "text", "content": "   "}}, "Content must not be empty."),
        ({"json": {"type": "pdf", "content": "x"}}, "Invalid analysis request."),
        ({"content": b"type=url", "headers": {"content-type": "text/plain"}}, "Invalid analysis request."),
    ],
)
def test_validation_errors_return_readable_string_detail(client, kwargs, detail):
    response = client.post("/api/analyze", **kwargs)

    assert response.status_code == 422
    assert response.json() == {"detail": detail}
