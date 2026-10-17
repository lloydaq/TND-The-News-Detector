import threading

from fastapi import APIRouter, HTTPException, status

from app.models.schemas import AnalysisResponse, AnalyzeRequest
from app.services.analyzer import analyze_content
from app.services.ollama_config import MAX_CONCURRENT_ANALYSES
from app.services.article_extractor import (
    ArticleContentError,
    ArticleFetchError,
    InvalidArticleURL,
    extract_article,
)

router = APIRouter()
_analysis_slots = threading.BoundedSemaphore(MAX_CONCURRENT_ANALYSES)


@router.post("/analyze", response_model=AnalysisResponse)
def analyze(request: AnalyzeRequest) -> AnalysisResponse:
    if not _analysis_slots.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Too many analyses are running. Please try again shortly.",
        )

    try:
        return _analyze(request)
    finally:
        _analysis_slots.release()


def _analyze(request: AnalyzeRequest) -> AnalysisResponse:
    if request.type == "url":
        try:
            article = extract_article(request.content)
        except InvalidArticleURL as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid URL.",
            ) from error
        except ArticleFetchError as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to fetch the external webpage.",
            ) from error
        except ArticleContentError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="No article content could be extracted.",
            ) from error
        try:
            return analyze_content(request, article)
        except RuntimeError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Ollama analysis is unavailable.",
            ) from error

    try:
        return analyze_content(request)
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ollama analysis is unavailable.",
        ) from error
