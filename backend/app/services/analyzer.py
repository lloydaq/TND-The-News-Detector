from app.models.schemas import AnalysisResponse, AnalyzeRequest
from app.services.article_extractor import ExtractedArticle


def analyze_content(
    request: AnalyzeRequest,
    article: ExtractedArticle | None = None,
) -> AnalysisResponse:
    """Return mock risk analysis while using real input/article metadata."""
    if article:
        title = article.title
        source = article.source
        publisher = article.publisher
        author = article.author
        published_at = article.published_at
    else:
        title = "Provided Text"
        source = "user-provided text"
        publisher = "User Provided"
        author = None
        published_at = None

    return AnalysisResponse(
        title=title,
        source=source,
        publisher=publisher,
        author=author,
        publishedAt=published_at,
        riskScore=78,
        riskLabel="Likely Misleading",
        sourceReliability="Moderate",
        signals=[
            {"name": "Sensational Language", "status": "warning"},
            {"name": "Unverified Claims", "status": "warning"},
            {"name": "Source Attribution", "status": "positive"},
        ],
        claims=[
            {
                "id": 1,
                "text": "Example claim from the article.",
                "status": "Needs Verification",
                "evidence": [
                    {
                        "source": "Example Source",
                        "description": "Example supporting information.",
                    }
                ],
            },
            {
                "id": 2,
                "text": "Another example claim.",
                "status": "Supported",
                "evidence": [
                    {
                        "source": "Example Source",
                        "description": "Example supporting evidence.",
                    }
                ],
            },
        ],
    )
