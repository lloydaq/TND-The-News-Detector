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
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(error),
            ) from error
        return analyze_content(request, article)

    return analyze_content(request)
