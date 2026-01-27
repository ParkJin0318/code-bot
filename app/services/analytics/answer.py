import asyncio
import logging
from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI
from langchain.schema import Document

from app.config import settings
from app.core.search import get_search
from app.services.analytics.data_source import get_analytics_data_source
from app.prompts import (
    EVENT_EXTRACTION_PROMPT,
    ANALYTICS_PROMPT,
    format_context,
    extract_sources,
)

logger = logging.getLogger(__name__)


class AnalyticsAnswerGenerator:

    _instance: Optional["AnalyticsAnswerGenerator"] = None

    def __new__(cls) -> "AnalyticsAnswerGenerator":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        logger.info("Initializing AnalyticsAnswerGenerator (singleton)...")

        self.llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0,
        )

        self.data_source = get_analytics_data_source()
        self.search = get_search()

        self._initialized = True
        logger.info("AnalyticsAnswerGenerator initialization complete")

    async def extract_event_name(self, question: str) -> Optional[str]:
        prompt = EVENT_EXTRACTION_PROMPT.format(question=question)

        response = await asyncio.to_thread(self.llm.invoke, prompt)
        event_name = str(response.content).strip()

        if event_name == "NONE" or not event_name:
            logger.warning(f"No event name found in question: {question}")
            return None

        logger.info(f"Extracted event name: {event_name}")
        return event_name

    def _format_analytics_data(self, data: Dict[str, Any]) -> str:
        if not data:
            return "데이터 없음"

        try:
            values = data.get("data", {}).get("values", {})

            if not values:
                return f"원본 데이터: {data}"

            lines = ["일별 이벤트 발생 횟수:"]
            total = 0

            for event_name, date_values in values.items():
                lines.append(f"\n이벤트: {event_name}")
                for date, count in sorted(date_values.items()):
                    lines.append(f"  {date}: {count:,}회")
                    total += count

            lines.append(f"\n총합: {total:,}회")
            return "\n".join(lines)

        except Exception as e:
            logger.warning(f"Failed to format analytics data: {e}")
            return f"원본 데이터: {data}"

    async def generate(self, question: str, days: int = 7) -> Dict[str, Any]:
        logger.info(f"Analyzing question: {question[:100]}... (days={days})")

        event_name = await self.extract_event_name(question)
        if not event_name:
            return {
                "answer": "질문에서 이벤트명을 찾지 못했어요. 분석할 이벤트명을 포함해서 다시 질문해주세요.\n\n예: `abc 이벤트 분석해줘`",
                "sources": [],
                "event_name": None,
            }

        analytics_data = {}
        try:
            analytics_data = await self.data_source.fetch_event_data(event_name, days=days)
        except Exception as e:
            logger.error(f"Failed to fetch analytics data: {e}")
            analytics_data = {"error": str(e)}

        search_query = f"{event_name} event tracking analytics"
        documents = await self.search.search(search_query, top_k=50, rerank_top_n=15)

        formatted_data = self._format_analytics_data(analytics_data)
        formatted_code = format_context(documents) if documents else "관련 코드를 찾지 못했습니다."

        prompt = ANALYTICS_PROMPT.format(
            event_name=event_name,
            analytics_data=formatted_data,
            code_context=formatted_code,
            question=question,
        )

        response = await asyncio.to_thread(self.llm.invoke, prompt)
        answer = str(response.content)

        sources = extract_sources(documents)
        logger.info(f"Generated analytics answer with {len(sources)} sources")

        return {
            "answer": answer,
            "sources": sources,
            "event_name": event_name,
        }


def get_analytics_answer_generator() -> AnalyticsAnswerGenerator:
    return AnalyticsAnswerGenerator()
