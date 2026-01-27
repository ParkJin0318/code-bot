import logging
from typing import Any, Dict, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class AnalyticsDataSource:

    _instance: Optional["AnalyticsDataSource"] = None

    def __new__(cls) -> "AnalyticsDataSource":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        logger.info("Initializing AnalyticsDataSource (singleton)...")
        self.gateway_url = settings.analytics_gateway_url
        self._initialized = True
        logger.info(f"AnalyticsDataSource initialized with gateway: {self.gateway_url}")

    async def fetch_event_data(self, event_name: str, days: int = 7, timeout: float = 30.0) -> Dict[str, Any]:
        url = f"{self.gateway_url}?event={event_name}&days={days}"
        logger.info(f"Fetching analytics data for event: {event_name} (days={days})")

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        logger.info(f"Received analytics data for event: {event_name}")
        return data


def get_analytics_data_source() -> AnalyticsDataSource:
    return AnalyticsDataSource()
