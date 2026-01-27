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
    format_context,
    extract_sources,
)

logger = logging.getLogger(__name__)


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
        
        self._initialized = True
        logger.info("CodebaseAnswerGenerator initialization complete")

    async def generate(self, question: str, documents: List[Document]) -> dict:
        logger.info(f"Generating answer for: {question[:100]}...")

        context = format_context(documents)
        prompt = self.prompt_template.format_messages(
            context=context,
            question=question,
        )

        response = await asyncio.to_thread(self.llm.invoke, prompt)
        answer = str(response.content)

        if answer.startswith(SECURITY_RESPONSE_PREFIX):
            logger.info("Security response triggered - hiding sources")
            return {"answer": answer, "sources": []}

        sources = extract_sources(documents)
        logger.info(f"Generated answer with {len(sources)} sources")

        return {
            "answer": answer,
            "sources": sources,
        }


def get_codebase_answer_generator() -> CodebaseAnswerGenerator:
    return CodebaseAnswerGenerator()
