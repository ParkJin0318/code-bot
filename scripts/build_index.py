#!/usr/bin/env python3
"""CLI script to build the codebase index for RAG search."""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings
from app.core.index import CodebaseIndexer


def setup_logging(log_level: str) -> None:
    """Configure logging for the indexing process."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )


def main() -> int:
    """Main entry point for the indexing CLI."""
    parser = argparse.ArgumentParser(
        description="Build the codebase index for RAG-based code search.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/build_index.py
  python scripts/build_index.py --codebase-path /path/to/project
  python scripts/build_index.py --reset  # Clear and rebuild index
        """,
    )
    parser.add_argument(
        "--codebase-path",
        type=str,
        default=str(settings.codebase_path),
        help=f"Path to the codebase to index (default: {settings.codebase_path})",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear existing index before rebuilding",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Maximum chunk size in characters (default: 1000)",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=200,
        help="Chunk overlap in characters (default: 200)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for adding documents (default: 100)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=settings.log_level,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help=f"Logging level (default: {settings.log_level})",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    # Validate codebase path
    codebase_path = Path(args.codebase_path)
    if not codebase_path.exists():
        logger.error(f"Codebase path does not exist: {codebase_path}")
        return 1

    if not codebase_path.is_dir():
        logger.error(f"Codebase path is not a directory: {codebase_path}")
        return 1

    logger.info("=" * 60)
    logger.info("Codebase Indexer")
    logger.info("=" * 60)
    logger.info(f"Codebase path: {codebase_path}")
    logger.info(f"Reset index: {args.reset}")
    logger.info(f"Chunk size: {args.chunk_size}")
    logger.info(f"Chunk overlap: {args.chunk_overlap}")
    logger.info(f"Batch size: {args.batch_size}")
    logger.info("=" * 60)

    try:
        # Create indexer
        indexer = CodebaseIndexer(
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )

        # Run indexing
        stats = indexer.index_codebase(
            codebase_path=codebase_path,
            reset=args.reset,
            batch_size=args.batch_size,
        )

        # Print summary
        logger.info("=" * 60)
        logger.info("Indexing Complete!")
        logger.info("=" * 60)
        logger.info(f"Files processed: {stats['files_processed']}")
        logger.info(f"Files skipped: {stats['files_skipped']}")
        logger.info(f"Chunks created: {stats['chunks_created']}")
        logger.info(f"Collection: {stats['collection_name']}")
        logger.info(f"Persist directory: {stats['persist_directory']}")
        logger.info("=" * 60)

        return 0

    except Exception as e:
        logger.exception(f"Indexing failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
