import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.search import get_search
from app.services.codebase.answer import get_codebase_answer_generator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


class CodebaseRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User question about the codebase")
    top_k: Optional[int] = Field(None, ge=1, le=500, description="Number of documents to retrieve before reranking")
    rerank_top_n: Optional[int] = Field(None, ge=1, le=100, description="Number of documents to keep after reranking")

    class Config:
        json_schema_extra = {
            "example": {
                "question": "What is the purpose of the MainActivity class?",
                "top_k": 20,
                "rerank_top_n": 15,
            }
        }


class ConfluenceDocumentResponse(BaseModel):
    title: str = Field(..., description="Document title")
    url: str = Field(..., description="Document URL")


class CodebaseResponse(BaseModel):
    answer: str = Field(..., description="Generated answer to the question")
    sources: List[str] = Field(default_factory=list, description="List of source files referenced")
    documents: List[ConfluenceDocumentResponse] = Field(default_factory=list, description="Related Confluence documents")

    class Config:
        json_schema_extra = {
            "example": {
                "answer": "MainActivity is the entry point of the Android application...",
                "sources": ["app/src/main/java/com/example/MainActivity.java"],
                "documents": [{"title": "Architecture Guide", "url": "https://..."}],
            }
        }


@router.post("/codebase", response_model=CodebaseResponse, status_code=status.HTTP_200_OK)
async def codebase_query(request: CodebaseRequest) -> CodebaseResponse:
    try:
        logger.info(f"Codebase request received: question='{request.question[:100]}...' top_k={request.top_k} rerank_top_n={request.rerank_top_n}")

        search = get_search()
        generator = get_codebase_answer_generator()

        try:
            documents = await search.search(request.question, top_k=request.top_k, rerank_top_n=request.rerank_top_n)
            if not documents:
                logger.warning(f"No documents retrieved for question: {request.question[:100]}...")
                return CodebaseResponse(
                    answer="죄송해요, 관련된 코드를 찾지 못했어요. 다른 키워드로 질문해주시겠어요?",
                    sources=[],
                    documents=[],
                )
            logger.info(f"Successfully retrieved {len(documents)} documents")
        except Exception as e:
            logger.error(f"Document retrieval failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve documents from database.",
            ) from e

        try:
            result = await generator.generate(request.question, documents)
            logger.info(f"Successfully generated answer with {len(result['sources'])} sources")
        except Exception as e:
            logger.error(f"Answer generation failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate answer. Check LLM API availability.",
            ) from e

        return CodebaseResponse(
            answer=result["answer"],
            sources=result["sources"],
            documents=result.get("documents", []),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error in codebase endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later.",
        ) from e


@router.get("/health", status_code=status.HTTP_200_OK)
async def health() -> dict:
    logger.debug("Health check requested")
    return {"status": "ok", "service": "code-bot-api"}
