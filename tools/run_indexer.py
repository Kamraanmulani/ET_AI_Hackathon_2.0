"""
tools/run_indexer.py — CLI script to run the full corpus indexer.

Usage from backend/:
    python ../tools/run_indexer.py [--force]

Or from project root:
    python tools/run_indexer.py [--force]

The indexer:
1. Reads all eligible chunks from MongoDB
2. Embeds via Ollama mxbai-embed-large
3. Upserts to Qdrant with deterministic point IDs
4. Projects asset/chunk nodes and edges to Neo4j
5. Skips unchanged chunks (idempotent by source_hash + chunk_version)

Run this after: a new importer pass, OCR review decisions, or Qdrant reinstall.
"""
from __future__ import annotations

import sys
import argparse
from pathlib import Path

# Add backend/ to Python path when running from project root
_BACKEND = Path(__file__).parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import os
os.chdir(_BACKEND)  # config.py loads .env relative to backend/

from app.core.logging import configure_logging
from app.core.config import settings

configure_logging("INFO")

import structlog
log = structlog.get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run the Pragyan RAG corpus indexer.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-index all chunks even if already indexed.",
    )
    args = parser.parse_args()

    log.info("run_indexer_started", force=args.force)

    from app.services.indexer import run_full_index
    summary = run_full_index(force=args.force)

    print("\n" + "=" * 60)
    print("PRAGYAN RAG INDEXER COMPLETE")
    print("=" * 60)
    print(f"  Total chunks: {summary['total']}")
    print(f"  Indexed:      {summary['indexed']}")
    print(f"  Skipped:      {summary['skipped']}")
    print(f"  Failed:       {summary['failed']}")
    print(f"  Job ID:       {summary['job_id']}")
    if summary['errors']:
        print("\nErrors:")
        for e in summary['errors']:
            print(f"  - {e}")
    print("=" * 60)

    if summary['failed'] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
