import asyncio
import logging
import re
from typing import List, Optional

from flashrank import Ranker, RerankRequest
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain.schema import Document

from app.config import settings

logger = logging.getLogger(__name__)


def _contains_korean(text: str) -> bool:
    return bool(re.search(r'[가-힣]', text))


async def _translate_query_to_english(query: str, llm: ChatOpenAI) -> str:
    if not _contains_korean(query):
        return query
    
    translation_prompt = f"""Translate this Korean question to English for searching Android/Kotlin codebase.
Focus on technical terms: class names, enum names, function names, patterns.
Output ONLY the English translation, nothing else.

Korean: {query}
English:"""
    
    try:
        response = await asyncio.to_thread(llm.invoke, translation_prompt)
        translated = str(response.content).strip()
        logger.info(f"Translated query: '{query}' -> '{translated}'")
        return translated
    except Exception as e:
        logger.warning(f"Translation failed, using original query: {e}")
        return query


class CodebaseSearch:

    _instance: Optional["CodebaseSearch"] = None

    def __new__(cls) -> "CodebaseSearch":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        logger.info("Initializing CodebaseSearch (singleton)...")
        
        self.embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={'device': settings.embedding_device, 'trust_remote_code': True},
            encode_kwargs={'normalize_embeddings': True},
        )
        logger.info(f"Loaded embedding model: {settings.embedding_model} (device: {settings.embedding_device})")
        
        self.vectorstore = Chroma(
            collection_name=settings.collection_name,
            embedding_function=self.embeddings,
            persist_directory=str(settings.chroma_db_path),
        )
        logger.info(f"Connected to ChromaDB: {settings.chroma_db_path}")
        
        self.reranker = Ranker(
            model_name=settings.rerank_model,
            max_length=settings.rerank_max_length
        )
        logger.info(f"Loaded reranker: {settings.rerank_model} (max_length={settings.rerank_max_length})")
        
        self.llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0,
        )
        logger.info("LLM client initialized for query translation")
        
        self._initialized = True
        logger.info("CodebaseSearch initialization complete")

    def _rerank_documents(
        self, 
        query: str, 
        documents: List[Document], 
        top_n: int
    ) -> List[Document]:
        if not documents:
            return []
        
        passages = [
            {"id": i, "text": doc.page_content, "meta": doc.metadata}
            for i, doc in enumerate(documents)
        ]
        
        rerank_request = RerankRequest(query=query, passages=passages)
        reranked = self.reranker.rerank(rerank_request)
        
        result = []
        for item in reranked[:top_n]:
            original_doc = documents[item["id"]]
            original_doc.metadata["rerank_score"] = item["score"]
            result.append(original_doc)
            
        logger.debug(f"Reranked {len(documents)} -> {len(result)} documents")
        return result

    async def search(
        self, 
        query: str, 
        top_k: Optional[int] = None,
        rerank_top_n: Optional[int] = None
    ) -> List[Document]:
        retrieve_k = top_k if top_k is not None else settings.retrieve_top_k
        final_n = rerank_top_n if rerank_top_n is not None else settings.rerank_top_n
        
        logger.info(f"Searching codebase: query='{query[:50]}...' retrieve_k={retrieve_k} rerank_top_n={final_n}")
        
        search_query = query
        if _contains_korean(query):
            search_query = await _translate_query_to_english(query, self.llm)
        
        results = await asyncio.to_thread(
            self.vectorstore.similarity_search_with_score,
            query=search_query,
            k=retrieve_k,
        )
        
        documents = []
        for doc, score in results:
            doc.metadata["similarity_score"] = score
            documents.append(doc)
        
        logger.info(f"Vector search returned {len(documents)} documents")
        
        if len(documents) > final_n:
            documents = await asyncio.to_thread(
                self._rerank_documents, search_query, documents, final_n
            )
            logger.info(f"Reranked to top {len(documents)} documents")
        
        return documents


def get_search() -> CodebaseSearch:
    return CodebaseSearch()
