"""Atlassian Confluence data source via n8n Gateway."""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ConfluenceDocument:
    """Confluence document search result."""

    title: str
    url: str
    excerpt: str
    space_name: str


@dataclass
class ConfluencePage:
    """Confluence page content."""

    page_id: str
    title: str
    content: str
    url: str


class AtlassianDataSource:
    """Client for Atlassian Confluence via n8n Gateway."""

    _instance: Optional["AtlassianDataSource"] = None

    def __new__(cls) -> "AtlassianDataSource":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        logger.info("Initializing AtlassianDataSource (singleton)...")
        self.search_url = settings.atlassian_search_url.rstrip("/")
        self.content_url = settings.atlassian_content_url.rstrip("/")
        self.timeout = 30.0
        self._initialized = True
        logger.info("AtlassianDataSource initialization complete")

    def _extract_page_id(self, url_or_id: str) -> Optional[str]:
        if url_or_id.isdigit():
            return url_or_id
        
        cloud_match = re.search(r"/pages/(\d+)", url_or_id)
        if cloud_match:
            return cloud_match.group(1)
        
        dc_match = re.search(r"pageId=(\d+)", url_or_id)
        if dc_match:
            return dc_match.group(1)
        
        return None

    async def fetch_page(self, page_id_or_url: str) -> Optional[ConfluencePage]:
        if not self.content_url:
            logger.warning("Atlassian content URL not configured")
            return None

        page_id = self._extract_page_id(page_id_or_url)
        if not page_id:
            logger.error(f"Could not extract page ID from: {page_id_or_url}")
            return None

        try:
            url = f"{self.content_url}/{page_id}"
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

            page = ConfluencePage(
                page_id=data.get("page_id", page_id),
                title=data.get("title", "Untitled"),
                content=data.get("content", ""),
                url=f"https://dramancompany.atlassian.net/wiki/pages/{page_id}",
            )
            logger.info(f"Fetched Confluence page: {page.title}")
            return page

        except httpx.TimeoutException:
            logger.error(f"Timeout while fetching Confluence page: {page_id}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from Gateway: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error fetching Confluence page: {e}")
            return None

    async def search(
        self,
        query: str,
        limit: int = 5,
    ) -> List[ConfluenceDocument]:
        if not self.search_url:
            logger.warning("Atlassian search URL not configured, skipping search")
            return []

        try:
            url = self.search_url
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params={
                        "query": query,
                        "limit": limit,
                    },
                )
                response.raise_for_status()
                data = response.json()

            documents = []
            results = data.get("results", [])
            base_url = data.get("_links", {}).get("base", "https://dramancompany.atlassian.net/wiki")
            
            for item in results:
                relative_url = item.get("url", "")
                full_url = f"{base_url}{relative_url}" if relative_url else ""
                space_name = item.get("resultGlobalContainer", {}).get("title", "")
                
                doc = ConfluenceDocument(
                    title=item.get("title", ""),
                    url=full_url,
                    excerpt=item.get("excerpt", ""),
                    space_name=space_name,
                )
                documents.append(doc)

            logger.info(f"Found {len(documents)} Confluence documents for: {query[:50]}...")
            return documents

        except httpx.TimeoutException:
            logger.error(f"Timeout while searching Confluence: {query[:50]}...")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from Atlassian Gateway: {e.response.status_code}")
            return []
        except Exception as e:
            logger.error(f"Error searching Confluence: {e}")
            return []


def get_atlassian_data_source() -> AtlassianDataSource:
    return AtlassianDataSource()
