import json

import httpx
import pytest

from app.models.schemas import AnalyzeRequest
from app.services import analyzer, evidence_verifier
from app.services.article_extractor import ExtractedArticle


class ResponseClient:
    response = None
    error = None

    def __init__(self, *args, **kwargs):
        self.timeout = kwargs["timeout"]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, json, **kwargs):
        if self.__class__.error:
            raise self.__class__.error
        return self.__class__.response


def _set_client(monkeypatch, response=None, error=None):
    ResponseClient.response = response
    ResponseClient.error = error
    monkeypatch.setattr(analyzer.httpx, "Client", ResponseClient)


def _response(body, status_code=200):
    return httpx.Response(
        status_code,
        json=body,
        request=httpx.Request("POST", "http://ollama.test/api/generate"),
    )


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (httpx.ConnectError("refused"), "Ollama connection failed"),
        (httpx.ReadTimeout("timed out"), "Ollama inference timed out"),
    ],
)
def test_initial_inference_failures_return_degraded_metadata(
    monkeypatch,
    error,
    reason,
):
    _set_client(monkeypatch, error=error)
    article = ExtractedArticle(
        title="Recovered title",
        text="A recovered article body.",
        source="https://example.test/article",
        publisher="Example",
    )

    result = analyzer.analyze_content(
        AnalyzeRequest(type="url", content=article.source),
        article,
    )

    assert result.analysis_status == "DEGRADED"
    assert reason in result.degradation_reasons
    assert result.title == "Recovered title"
    assert result.publisher == "Example"
    assert result.claims == []


@pytest.mark.parametrize(
    "body",
    [
        {"response": ""},
        {"response": json.dumps({"signals": []})},
        {"response": json.dumps({"sourceReliability": "Unknown", "signals": {}})},
        {"unexpected": "wrapper"},
    ],
)
def test_invalid_initial_model_outputs_are_degraded(monkeypatch, body):
    _set_client(monkeypatch, response=_response(body))

    result = analyzer.analyze_content(
        AnalyzeRequest(type="text", content="A factual article claim.")
    )

    assert result.analysis_status == "DEGRADED"
    assert result.claims == []
    assert result.degradation_reasons
    assert all("response" not in reason.lower() for reason in result.degradation_reasons)


def test_http_model_failure_is_sanitized(monkeypatch):
    _set_client(monkeypatch, response=_response({"error": "model not found"}, 404))

    result = analyzer.analyze_content(
        AnalyzeRequest(type="text", content="A factual article claim.")
    )

    assert result.analysis_status == "DEGRADED"
    assert result.degradation_reasons == ["Ollama model is unavailable"]


def test_verifier_uses_remaining_timeout_and_preserves_evidence(monkeypatch):
    captured = {}

    class CapturingClient(ResponseClient):
        def __init__(self, *args, **kwargs):
            captured["timeout"] = kwargs["timeout"]
            super().__init__(*args, **kwargs)

    ResponseClient.response = _response({"response": json.dumps({"assessments": []})})
    ResponseClient.error = None
    monkeypatch.setattr(evidence_verifier.httpx, "Client", CapturingClient)

    evidence = [
        {
            "source": "Example",
            "description": "A headline",
            "url": "https://example.test/article",
        }
    ]
    result = evidence_verifier.verify_evidence(
        "A factual claim",
        evidence,
        timeout_seconds=0.25,
    )

    assert captured["timeout"] == 0.25
    assert result.evidence[0].url == evidence[0]["url"]
    assert result.verification_status == "INSUFFICIENT_EVIDENCE"
