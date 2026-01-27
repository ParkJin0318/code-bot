"""FastAPI application for n8n Slack bot integration."""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse

from app.api.routes import router
from app.config import settings

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Code Bot API")
    logger.info(f"API Server: {settings.api_host}:{settings.api_port}")
    logger.info(f"Codebase Path: {settings.codebase_path}")
    logger.info(f"ChromaDB Path: {settings.chroma_db_path}")
    yield
    logger.info("Shutting down Code Bot API")


app = FastAPI(
    title="Code Bot",
    description="RAG-based Q&A for any codebase via n8n Slack integration",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url="/api/redoc",
    lifespan=lifespan,
    default_response_class=ORJSONResponse,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=500)

app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting uvicorn server on {settings.api_host}:{settings.api_port}")
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower(),
    )
