import json as json_lib

import httpx

from app.models.schemas import AnalyzeRequest
from app.services import analyzer
from app.services.evidence_verifier import VerificationResult


class OllamaClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, json, **kwargs):
        return httpx.Response(
            200,
            json={
                "response": json_lib.dumps(
                    {
                        "sourceReliability": "Unknown",
                        "signals": [],
                        "claims": [
                            {"id": 1, "text": "ISRO launched a satellite."},
                            {"id": 2, "text": "The mission began in 2026."},
                        ],
                    }
                )
            },
            request=httpx.Request("POST", url),
        )


def test_analyzer_attaches_evidence_to_each_claim_and_preserves_status(
    monkeypatch,
):
    searched_claims = []

    def fake_search_evidence(claim_text, limit):
        searched_claims.append((claim_text, limit))
        return [
            {
                "source": "Publisher",
                "description": f"Evidence for {claim_text}",
                "url": "https://example.test/evidence",
            }
        ]

    monkeypatch.setattr(analyzer.httpx, "Client", OllamaClient)
    monkeypatch.setattr(analyzer, "search_evidence", fake_search_evidence)
    monkeypatch.setattr(
        analyzer,
        "retrieve_evidence_content",
        lambda evidence, cache, max_articles: evidence,
    )
    monkeypatch.setattr(
        analyzer,
        "verify_evidence",
        lambda claim, evidence, max_articles: VerificationResult(
            evidence=[],
            verificationStatus="UNVERIFIED",
        ),
    )

    response = analyzer.analyze_content(
        AnalyzeRequest(type="text", content="A news report with claims.")
    )

    assert searched_claims == [
        ("ISRO launched a satellite.", 3),
        ("The mission began in 2026.", 3),
    ]
    assert len(response.claims) == 2
    assert all(claim.status == "Needs Verification" for claim in response.claims)
    assert response.claims[0].evidence[0].source == "Publisher"
    assert response.claims[0].verification_status == "INSUFFICIENT_EVIDENCE"
    assert response.model_dump(by_alias=True)["claims"][0]["evidence"][0][
        "url"
    ] == "https://example.test/evidence"


class EvidenceVerifierOllamaClient:
    calls = 0

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, json, **kwargs):
        self.__class__.calls += 1
        if self.__class__.calls == 1:
            response = {
                "sourceReliability": "Unknown",
                "signals": [],
                "claims": [
                    {"id": 1, "text": "ISRO launched a satellite."},
                ],
            }
        else:
            response = {
                "assessments": [
                    {
                        "articleIndex": 1,
                        "relevance": "RELATED_ONLY",
                        "explanation": (
                            "The article discusses a related topic, "
                            "but the available information does not "
                            "establish or directlyrefute the specific "
                            "claim."
                        ),
                    }
                ]
            }
        return httpx.Response(
            200,
            json={"response": json_lib.dumps(response)},
            request=httpx.Request("POST", url),
        )


def test_analyzer_response_path_normalizes_public_evidence_explanation(
    monkeypatch,
):
    EvidenceVerifierOllamaClient.calls = 0
    monkeypatch.setattr(
        analyzer.httpx,
        "Client",
        EvidenceVerifierOllamaClient,
    )
    monkeypatch.setattr(
        analyzer,
        "search_evidence",
        lambda claim_text, limit: [
            {
                "source": "Publisher",
                "description": "ISRO tests satellite communication technology",
                "url": "https://example.test/evidence",
            }
        ],
    )
    monkeypatch.setattr(
        analyzer,
        "retrieve_evidence_content",
        lambda evidence, cache, max_articles: [
            {
                **evidence[0],
                "contentStatus": "FETCHED",
                "_content": (
                    "ISRO tested quantum communication technology for "
                    "future satellite links."
                ),
            }
        ],
    )

    response = analyzer.analyze_content(
        AnalyzeRequest(type="text", content="A news report with claims.")
    )
    public_response = response.model_dump(by_alias=True)

    evidence = public_response["claims"][0]["evidence"][0]
    assert evidence["relevance"] == "RELATED_ONLY"
    assert evidence["explanation"] == (
        "The article discusses a related topic, but the available "
        "information does not establish or directly refute the specific "
        "claim."
    )
    assert public_response["claims"][0]["verificationStatus"] == "INSUFFICIENT_EVIDENCE"
    assert public_response["claims"][0]["status"] == "Needs Verification"
