from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    type: Literal["url", "text"]
    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def content_must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("content cannot be empty")
        return value


class Signal(BaseModel):
    name: str
    status: str


class Evidence(BaseModel):
    source: str
    description: str


class Claim(BaseModel):
    id: int
    text: str
    status: str
    evidence: list[Evidence]


class AnalysisResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str
    source: str
    publisher: str
    author: str | None = None
    published_at: str | None = Field(default=None, alias="publishedAt")
    risk_score: int = Field(alias="riskScore")
    risk_label: str = Field(alias="riskLabel")
    source_reliability: str = Field(alias="sourceReliability")
    signals: list[Signal]
    claims: list[Claim]
