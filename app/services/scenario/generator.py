import asyncio
import logging
from typing import List, Optional

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import Document

from app.config import settings
from app.core.search import get_search
from app.prompts.utils import format_context
from app.prompts.keyword import SCENARIO_KEYWORD_PROMPT
from app.prompts.user_scenario import USER_SCENARIO_PROMPT
from app.services.atlassian.data_source import get_atlassian_data_source

logger = logging.getLogger(__name__)


class ScenarioGenerator:
    """기획서 + 코드베이스 기반 QA 시나리오 생성기"""

    _instance: Optional["ScenarioGenerator"] = None

    def __new__(cls) -> "ScenarioGenerator":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        logger.info("Initializing ScenarioGenerator (singleton)...")

        self.llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0,
        )
        self.scenario_template = ChatPromptTemplate.from_template(USER_SCENARIO_PROMPT)
        self.keyword_template = ChatPromptTemplate.from_template(SCENARIO_KEYWORD_PROMPT)
        self.search = get_search()

        self._initialized = True
        logger.info("ScenarioGenerator initialization complete")

    async def _extract_keywords(self, spec_title: str, spec_content: str) -> str:
        """기획서에서 코드베이스 검색용 키워드 추출"""
        content_preview = spec_content[:2000] if len(spec_content) > 2000 else spec_content
        
        prompt = self.keyword_template.format_messages(
            spec_title=spec_title,
            spec_content=content_preview,
        )
        response = await asyncio.to_thread(self.llm.invoke, prompt)
        keywords = str(response.content).strip()
        logger.info(f"Extracted keywords for scenario: {keywords}")
        return keywords

    async def _search_codebase(self, keywords: str, top_k: int = 15) -> List[Document]:
        """키워드로 코드베이스 검색"""
        try:
            documents = await self.search.search(keywords, top_k=top_k, rerank_top_n=10)
            logger.info(f"Found {len(documents)} relevant code documents")
            return documents
        except Exception as e:
            logger.warning(f"Codebase search failed: {e}")
            return []

    async def generate(
        self,
        spec_title: str,
        spec_content: str,
        additional_keywords: Optional[str] = None,
    ) -> dict:
        """기획서 + 코드베이스 기반 QA 시나리오 생성"""
        logger.info(f"Generating QA scenario for: {spec_title}")

        # 1. 키워드 추출
        keywords = await self._extract_keywords(spec_title, spec_content)
        if additional_keywords:
            keywords = f"{keywords}, {additional_keywords}"

        # 2. 코드베이스 검색
        code_documents = await self._search_codebase(keywords)
        code_context = format_context(code_documents) if code_documents else "관련 코드를 찾지 못했습니다."

        # 3. 시나리오 생성
        prompt = self.scenario_template.format_messages(
            spec_title=spec_title,
            spec_content=spec_content,
            code_context=code_context,
        )

        response = await asyncio.to_thread(self.llm.invoke, prompt)
        scenario = str(response.content)

        # 4. 소스 파일 추출
        sources = []
        if code_documents:
            seen = set()
            for doc in code_documents:
                file_path = doc.metadata.get("file_path", "unknown")
                if file_path not in seen:
                    seen.add(file_path)
                    sources.append(file_path)

        logger.info(f"Generated QA scenario with {len(sources)} code references")

        return {
            "scenario": scenario,
            "sources": sources,
            "keywords_used": keywords,
        }

    async def fetch_and_generate(
        self,
        page_id_or_url: str,
        additional_keywords: Optional[str] = None,
    ) -> Optional[dict]:
        logger.info(f"Fetching Confluence page: {page_id_or_url}")

        atlassian = get_atlassian_data_source()
        page = await atlassian.fetch_page(page_id_or_url)

        if page is None:
            logger.error(f"Failed to fetch Confluence page: {page_id_or_url}")
            return None

        return await self.generate(
            spec_title=page.title,
            spec_content=page.content,
            additional_keywords=additional_keywords,
        )


def get_scenario_generator() -> ScenarioGenerator:
    return ScenarioGenerator()
