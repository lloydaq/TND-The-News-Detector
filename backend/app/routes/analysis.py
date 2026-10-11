from fastapi import APIRouter, HTTPException, status

from app.models.schemas import AnalysisResponse, AnalyzeRequest
from app.services.analyzer import analyze_content
from app.services.article_extractor import (
    ArticleContentError,
    ArticleFetchError,
    InvalidArticleURL,
    extract_article,
)

router = APIRouter()


@router.post("/analyze", response_model=AnalysisResponse)
def analyze(request: AnalyzeRequest) -> AnalysisResponse:
    if request.type == "url":
        try:
            article = extract_article(request.content)
        except InvalidArticleURL as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error),
            ) from error
        except ArticleFetchError as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(error),
            ) from error
        except ArticleContentError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        try:
            return analyze_content(request, article)
        except RuntimeError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(error),
            ) from error

    try:
        return analyze_content(request)
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

