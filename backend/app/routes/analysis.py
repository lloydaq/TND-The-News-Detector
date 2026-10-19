import threading
import logging
import time

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
logger = logging.getLogger(__name__)


@router.post("/analyze", response_model=AnalysisResponse)
def analyze(request: AnalyzeRequest) -> AnalysisResponse:
    if not _analysis_slots.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Too many analyses are running. Please try again shortly.",
        )

    try:
        return _analyze(request)
    except HTTPException:
        raise
    except Exception as error:
        # Raised as an HTTPException so the response is JSON and passes through
        # CORS; the default 500 handler sits outside the CORS middleware.
        logger.exception("Unexpected analysis failure (%s).", type(error).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The analysis failed unexpectedly. Please try again.",
        ) from error
    finally:
        _analysis_slots.release()


def _analyze(request: AnalyzeRequest) -> AnalysisResponse:
    started_at = time.monotonic()
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
            result = analyze_content(request, article)
            logger.info(
                "API analysis request completed in %.3fs (type=url, status=%s).",
                time.monotonic() - started_at,
                result.analysis_status,
            )
            return result
        except RuntimeError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Ollama analysis is unavailable.",
            ) from error

    try:
        result = analyze_content(request)
        logger.info(
            "API analysis request completed in %.3fs (type=text, status=%s).",
            time.monotonic() - started_at,
            result.analysis_status,
        )
        return result
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ollama analysis is unavailable.",
        ) from error
