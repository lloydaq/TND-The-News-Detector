from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    type: Literal["url", "text"]
    content: str = Field(min_length=1, max_length=100_000)

    @field_validator("content")
    @classmethod
    def content_must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("content cannot be empty")
        return value



class Signal(BaseModel):
    name: str
    status: Literal["positive", "warning", "unknown"]



class Evidence(BaseModel): 
    source: str
    description: str
    url: str | None = None
    provider: str | None = None
    providers: list[str] | None = None
    duplicate_urls: list[str] | None = Field(default=None, alias="duplicateUrls")
    published_at: str | None = Field(default=None, alias="publishedAt")
    evidence_type: Literal["HEADLINE_ONLY", "ARTICLE_TEXT"] | None = Field(
        default=None,
        alias="evidenceType",
    )
    source_quality: dict[str, bool | str] | None = Field(
        default=None,
        alias="sourceQuality",
    )
    independence: Literal["UNKNOWN", "SAME_ARTICLE"] | None = None
    content_status: Literal[
        "FETCHED",
        "UNAVAILABLE",
        "BLOCKED",
        "UNSUPPORTED_CONTENT",
    ] | None = Field(default=None, alias="contentStatus")
    relevance: Literal[
        "SUPPORTS",
        "CONTRADICTS",
        "RELATED_ONLY",
        "INSUFFICIENT_INFORMATION",
    ] | None = None
    explanation: str | None = None

class Claim(BaseModel):
    id: int
    text: str
    status: str
    evidence: list[Evidence]
    verification_status: Literal[
        "SUPPORTED",
        "CONTRADICTED",
        "INSUFFICIENT_EVIDENCE",
        "MIXED",
        "UNVERIFIABLE",
    ] = Field(default="INSUFFICIENT_EVIDENCE", alias="verificationStatus")

    @field_validator("verification_status", mode="before")
    @classmethod
    def normalize_legacy_verification_status(cls, value: str) -> str:
        """Accept Phase 3 names while exposing the Phase 4 vocabulary."""

        return {
            "MIXED_EVIDENCE": "MIXED",
            "UNVERIFIED": "INSUFFICIENT_EVIDENCE",
        }.get(value, value)


class AnalysisResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str
    source: str
    publisher: str
    author: str | None = None
    published_at: str | None = Field(default=None, alias="publishedAt")
    risk_score: int = Field(ge=0, le=100, alias="riskScore")
    risk_label: Literal["Low Risk", "Needs Verification", "High Risk"] = Field(
        alias="riskLabel"
    )
    source_reliability: Literal["Unknown", "Low", "Moderate", "High"] = Field(
        alias="sourceReliability"
    )
    signals: list[Signal]
    claims: list[Claim]
    analysis_status: Literal["COMPLETE", "DEGRADED"] = Field(
        default="COMPLETE",
        alias="analysisStatus",
    )
    degradation_reasons: list[str] = Field(
        default_factory=list,
        alias="degradationReasons",
    )
    analysis_explanation: str = Field(
        default="Risk score is a heuristic warning indicator, not a probability of misinformation.",
        alias="analysisExplanation",
    )
