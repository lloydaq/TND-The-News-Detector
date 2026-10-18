from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.models.schemas import AnalysisResponse, Claim, Evidence, Signal
from app.services.article_extractor import (
    ArticleContentError,
    ArticleFetchError,
    ExtractedArticle,
    InvalidArticleURL,
)
from app.services.article_extractor import _SafeNetworkBackend
from httpcore._backends.sync import SyncStream


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ok", "service": "TND Backend"}


def test_cors_headers_allowed_origin(client):
    response = client.options(
        "/api/analyze",
        headers={
            "Origin": "http://localhost:5500",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5500"


def test_cors_does_not_allow_null_origin(client):
    response = client.options(
        "/api/analyze",
        headers={
            "Origin": "null",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers.get("access-control-allow-origin") is None


def test_analyze_empty_payload_rejected(client):
    response = client.post("/api/analyze", json={})
    assert response.status_code == 422


def test_analyze_blank_content_rejected(client):
    response = client.post("/api/analyze", json={"type": "text", "content": "   "})
    assert response.status_code == 422


def test_analyze_invalid_type_rejected(client):
    response = client.post("/api/analyze", json={"type": "invalid", "content": "Sample text"})
    assert response.status_code == 422


def test_analyze_content_too_long_rejected(client):
    response = client.post("/api/analyze", json={"type": "text", "content": "A" * 100_001})
    assert response.status_code == 422


def test_analyze_request_body_limit_rejects_oversized_ignored_fields(client):
    response = client.post(
        "/api/analyze",
        json={
            "type": "text",
            "content": "valid",
            "ignored": "x" * 600_000,
        },
    )
    assert response.status_code == 413
    assert response.json() == {"detail": "Request body is too large."}


def test_analysis_response_invariants_are_enforced():
    with pytest.raises(ValueError):
        AnalysisResponse(
            title="Title",
            source="Source",
            publisher="Publisher",
            riskScore=101,
            riskLabel="High Risk",
            sourceReliability="Unknown",
            signals=[],
            claims=[],
        )


def test_analyze_text_valid_payload_and_response_schema(client, monkeypatch):
    def fake_analyze_content(request, article=None):
        return AnalysisResponse(
            title="Provided Text",
            source="user-provided text",
            publisher="User Provided",
            author=None,
            publishedAt=None,
            riskScore=45,
            riskLabel="Needs Verification",
            sourceReliability="Unknown",
            signals=[
                Signal(name="Sensational Language", status="positive"),
            ],
            claims=[
                Claim(
                    id=1,
                    text="NASA confirmed water ice on the Moon.",
                    status="Needs Verification",
                    evidence=[
                        Evidence(
                            source="Phys.org",
                            description="NASA lunar study",
                            url="https://example.test/study",
                            contentStatus="FETCHED",
                            relevance="SUPPORTS",
                            explanation="The article directly states NASA confirmed water ice.",
                        )
                    ],
                    verificationStatus="SUPPORTED",
                )
            ],
        )

    monkeypatch.setattr("app.routes.analysis.analyze_content", fake_analyze_content)

    response = client.post(
        "/api/analyze",
        json={"type": "text", "content": "NASA confirmed water ice on the Moon."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["riskScore"] == 45
    assert data["riskLabel"] == "Needs Verification"
    assert data["sourceReliability"] == "Unknown"
    assert len(data["signals"]) == 1
    assert len(data["claims"]) == 1
    assert data["claims"][0]["verificationStatus"] == "SUPPORTED"
    assert data["claims"][0]["evidence"][0]["relevance"] == "SUPPORTS"
    assert isinstance(data["analysisExplanation"], str)


def test_analyze_url_invalid_url_returns_400(client, monkeypatch):
    def failing_extract(url):
        raise InvalidArticleURL("Invalid URL.")

    monkeypatch.setattr("app.routes.analysis.extract_article", failing_extract)

    response = client.post(
        "/api/analyze",
        json={"type": "url", "content": "http://localhost/secret"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid URL."


def test_analyze_url_fetch_error_returns_502(client, monkeypatch):
    def failing_extract(url):
        raise ArticleFetchError("Unable to fetch external webpage.")

    monkeypatch.setattr("app.routes.analysis.extract_article", failing_extract)

    response = client.post(
        "/api/analyze",
        json={"type": "url", "content": "https://example.test/unavailable"},
    )
    assert response.status_code == 502
    assert "Unable to fetch" in response.json()["detail"]


def test_analyze_url_content_error_returns_422(client, monkeypatch):
    def failing_extract(url):
        raise ArticleContentError("No article content found.")

    monkeypatch.setattr("app.routes.analysis.extract_article", failing_extract)

    response = client.post(
        "/api/analyze",
        json={"type": "url", "content": "https://example.test/empty"},
    )
    assert response.status_code == 422
    assert "No article content" in response.json()["detail"]


def test_analyze_runtime_error_returns_503(client, monkeypatch):
    def failing_analyze(request, article=None):
        raise RuntimeError("Local AI analysis failed. Check that Ollama is running.")

    monkeypatch.setattr("app.routes.analysis.analyze_content", failing_analyze)

    response = client.post(
        "/api/analyze",
        json={"type": "text", "content": "Sample text for testing."},
    )
    assert response.status_code == 503
    assert "Ollama" in response.json()["detail"]
    assert "Local AI" not in response.json()["detail"]


def test_safe_network_backend_returns_httpcore_sync_stream(monkeypatch):
    class FakeSocket:
        def __init__(self, *_args):
            self.connected_to = None

        def settimeout(self, _timeout):
            pass

        def connect(self, address):
            self.connected_to = address

        def setsockopt(self, *_args):
            pass

        def close(self):
            pass

    fake_socket = FakeSocket()
    monkeypatch.setattr(
        "app.services.article_extractor._public_addresses",
        lambda _host: ["93.184.216.34"],
    )
    monkeypatch.setattr(
        "app.services.article_extractor.socket.socket",
        lambda *_args: fake_socket,
    )

    stream = _SafeNetworkBackend().connect_tcp("example.test", 443, timeout=1)

    assert isinstance(stream, SyncStream)
    assert fake_socket.connected_to == ("93.184.216.34", 443)
