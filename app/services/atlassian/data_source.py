"""Atlassian Confluence data source via n8n Gateway."""

import logging
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


class AtlassianDataSource:
    """Client for Atlassian Confluence search via n8n Gateway."""

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
        self.gateway_url = settings.atlassian_gateway_url
        self.timeout = 30.0
        self._initialized = True
        logger.info("AtlassianDataSource initialization complete")

    async def search(
        self,
        query: str,
        limit: int = 5,
    ) -> List[ConfluenceDocument]:
        """Search Confluence documents via n8n Gateway.
        
        Args:
            query: Search query string
            limit: Maximum number of results to return
            
        Returns:
            List of ConfluenceDocument objects
        """
        if not self.gateway_url:
            logger.warning("Atlassian gateway URL not configured, skipping search")
            return []

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    self.gateway_url,
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
    """Get singleton instance of AtlassianDataSource."""
    return AtlassianDataSource()
