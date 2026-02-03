import asyncio
import logging
from typing import List, Optional

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import Document

from app.config import settings
from app.prompts import (
    CODEBASE_PROMPT,
    SECURITY_RESPONSE_PREFIX,
    KEYWORD_EXTRACTION_PROMPT,
    DOCUMENT_RELEVANCE_PROMPT,
    format_context,
    extract_sources,
)
from app.services.atlassian import get_atlassian_data_source, ConfluenceDocument

logger = logging.getLogger(__name__)


def format_confluence_documents(docs: List[ConfluenceDocument]) -> str:
    if not docs:
        return "관련 문서 없음"
    
    lines = []
    for doc in docs:
        lines.append(f"- {doc.title}: {doc.excerpt[:200]}... (링크: {doc.url})")
    return "\n".join(lines)


def format_confluence_sources(docs: List[ConfluenceDocument]) -> List[dict]:
    return [{"title": doc.title, "url": doc.url} for doc in docs]


def format_documents_for_relevance(docs: List[ConfluenceDocument]) -> str:
    lines = []
    for i, doc in enumerate(docs, 1):
        excerpt = doc.excerpt[:150].replace("\n", " ") if doc.excerpt else ""
        lines.append(f"{i}. [{doc.title}] {excerpt}")
    return "\n".join(lines)


class CodebaseAnswerGenerator:

    _instance: Optional["CodebaseAnswerGenerator"] = None

    def __new__(cls) -> "CodebaseAnswerGenerator":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        logger.info("Initializing CodebaseAnswerGenerator (singleton)...")
        
        self.llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0,
        )
        self.prompt_template = ChatPromptTemplate.from_template(CODEBASE_PROMPT)
        self.keyword_template = ChatPromptTemplate.from_template(KEYWORD_EXTRACTION_PROMPT)
        self.relevance_template = ChatPromptTemplate.from_template(DOCUMENT_RELEVANCE_PROMPT)
        self.atlassian = get_atlassian_data_source()
        
        self._initialized = True
        logger.info("CodebaseAnswerGenerator initialization complete")

    async def _extract_keywords(self, question: str) -> str:
        prompt = self.keyword_template.format_messages(question=question)
        response = await asyncio.to_thread(self.llm.invoke, prompt)
        keywords = str(response.content).strip()
        logger.info(f"Extracted keywords: {keywords}")
        return keywords

    async def _filter_relevant_documents(
        self, question: str, docs: List[ConfluenceDocument]
    ) -> List[ConfluenceDocument]:
        if not docs:
            return []
        
        documents_text = format_documents_for_relevance(docs)
        prompt = self.relevance_template.format_messages(
            question=question,
            documents=documents_text,
        )
        response = await asyncio.to_thread(self.llm.invoke, prompt)
        result = str(response.content).strip()
        
        logger.info(f"Relevance filter result: {result}")
        
        if result == "없음" or not result:
            return []
        
        try:
            indices = [int(x.strip()) - 1 for x in result.split(",") if x.strip().isdigit()]
            filtered = [docs[i] for i in indices if 0 <= i < len(docs)]
            logger.info(f"Filtered to {len(filtered)} relevant documents")
            return filtered
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse relevance result: {e}")
            return docs[:3]

    async def _search_confluence(self, question: str) -> List[ConfluenceDocument]:
        keywords = await self._extract_keywords(question)
        all_docs = await self.atlassian.search(keywords, limit=30)
        
        if not all_docs:
            return []
        
        relevant_docs = await self._filter_relevant_documents(question, all_docs)
        return relevant_docs

    async def generate(self, question: str, documents: List[Document]) -> dict:
        logger.info(f"Generating answer for: {question[:100]}...")

        confluence_docs = await self._search_confluence(question)
        
        context = format_context(documents)
        documents_context = format_confluence_documents(confluence_docs)
        
        prompt = self.prompt_template.format_messages(
            context=context,
            documents=documents_context,
            question=question,
        )

        response = await asyncio.to_thread(self.llm.invoke, prompt)
        answer = str(response.content)

        if answer.startswith(SECURITY_RESPONSE_PREFIX):
            logger.info("Security response triggered - hiding sources")
            return {"answer": answer, "sources": [], "documents": []}

        sources = extract_sources(documents)
        doc_sources = format_confluence_sources(confluence_docs)
        logger.info(f"Generated answer with {len(sources)} code sources and {len(doc_sources)} documents")

        return {
            "answer": answer,
            "sources": sources,
            "documents": doc_sources,
        }


def get_codebase_answer_generator() -> CodebaseAnswerGenerator:
    return CodebaseAnswerGenerator()
