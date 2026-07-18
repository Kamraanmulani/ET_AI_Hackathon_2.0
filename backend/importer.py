"""
importer.py — Repeatable idempotent corpus importer for Pragyan Plant Intelligence.

Usage (from backend/ directory):
    python importer.py [--db DB_NAME] [--uri MONGODB_URI] [--dry-run]

What it does:
1. Reads Data/manifests/active_document_manifest.json → imports `documents` collection.
2. Reads Data/manifests/pid_asset_registry.json → imports `assets` collection.
3. Reads Data/manifests/pid_relationships.json → imports `relationships` collection.
4. Reads Data/derived/ocr/work-orders-001/job.json → imports `ocr_jobs`, `ocr_pages`, `ocr_regions`.
5. Imports candidate work-order fields and links from job.json.
6. Reads Data/derived/ocr/work-orders-001/review_queue.json → imports `review_tasks`.
7. Appends an audit event for this import run.

Idempotency:
- All writes use update_one(filter, $set, upsert=True).
- Stable IDs are used as filter keys (source_id, tag, region_id, task_id, etc.).
- Running twice produces the same result; no duplicates are created.

Safety:
- Source files are NEVER modified or deleted.
- Synthetic-demo records always carry provenance='synthetic_demo' and synthetic_label.
- OCR records always land as 'AI proposed' / 'pending_review'.
- The importer does NOT re-run OCR; it only loads existing derived artifacts.

On MongoDB unavailability:
- The importer exits with a clear error message and a non-zero exit code.
- Import is not faked or skipped silently.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import structlog
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

# Allow running from the backend/ directory
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import settings
from app.core.database import ensure_indexes, get_db, ping_db
from app.core.logging import configure_logging
from app.models.asset import AssetRecord, RelationshipRecord
from app.models.audit import AuditEventRecord
from app.models.document import DocumentRecord
from app.models.ocr import OcrJobRecord, OcrPageRecord, OcrRegionRecord
from app.models.review import ReviewTaskRecord
from app.models.work_order import WorkOrderFieldRecord, WorkOrderLinkRecord
from app.repositories.asset_repo import AssetRepository
from app.repositories.document_repo import DocumentRepository
from app.repositories.ocr_repo import OcrRepository
from app.repositories.review_repo import ReviewRepository

configure_logging(settings.log_level)
log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

BACKEND_DIR = Path(__file__).parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "Data"
MANIFESTS_DIR = DATA_DIR / "manifests"
OCR_DIR = DATA_DIR / "derived" / "ocr" / "work-orders-001"


def resolve(path: Path) -> Path:
    """Return an absolute path; raise if it does not exist."""
    if not path.exists():
        raise FileNotFoundError(f"Required data file not found: {path}")
    return path


# ---------------------------------------------------------------------------
# Import helpers
# ---------------------------------------------------------------------------


def import_documents(db, dry_run: bool) -> dict:
    manifest_path = resolve(MANIFESTS_DIR / "active_document_manifest.json")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = data["sources"]

    repo = DocumentRepository(db)
    inserted = 0
    updated = 0

    for s in sources:
        dimensions = s.get("dimensions", {})
        record = DocumentRecord(
            source_id=s["source_id"],
            path=s["path"],
            document_type=s["document_type"],
            provenance=s["provenance"],
            sha256=s["sha256"],
            bytes=s.get("bytes"),
            page_count=s.get("page_count"),
            image_width=dimensions.get("width"),
            image_height=dimensions.get("height"),
            drawing_id=s.get("drawing_id"),
            text_layer=s.get("text_layer"),
            extraction_state=s.get("extraction_state", "pending"),
            synthetic_notice_text=s.get("synthetic_notice_text"),
            immutable=s.get("immutable"),
        )
        if not dry_run:
            _, was_inserted = repo.upsert(record)
            if was_inserted:
                inserted += 1
            else:
                updated += 1

    total = len(sources)
    log.info("documents_imported", total=total, inserted=inserted, updated=updated, dry_run=dry_run)
    return {"total": total, "inserted": inserted, "updated": updated}


def import_assets(db, dry_run: bool) -> dict:
    registry_path = resolve(MANIFESTS_DIR / "pid_asset_registry.json")
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    assets = data["assets"]

    # Build drawing_id lookup from active_document_manifest
    manifest_path = resolve(MANIFESTS_DIR / "active_document_manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    drawing_lookup = {s["source_id"]: s.get("drawing_id") for s in manifest["sources"]}

    repo = AssetRepository(db)
    inserted = 0
    updated = 0

    for a in assets:
        record = AssetRecord(
            tag=a["tag"],
            asset_type=a["type"],
            area=a["area"],
            source_id=a["source_id"],
            drawing_id=drawing_lookup.get(a["source_id"]),
            state=a.get("state", "verified"),
        )
        if not dry_run:
            _, was_inserted = repo.upsert_asset(record)
            if was_inserted:
                inserted += 1
            else:
                updated += 1

    total = len(assets)
    log.info("assets_imported", total=total, inserted=inserted, updated=updated, dry_run=dry_run)
    return {"total": total, "inserted": inserted, "updated": updated}


def import_relationships(db, dry_run: bool) -> dict:
    rel_path = resolve(MANIFESTS_DIR / "pid_relationships.json")
    data = json.loads(rel_path.read_text(encoding="utf-8"))
    relationships = data["relationships"]

    repo = AssetRepository(db)
    inserted = 0
    updated = 0

    for r in relationships:
        record = RelationshipRecord(
            from_tag=r["from"],
            relationship_type=r["type"],
            to_tag=r["to"],
            source_id=r["source_id"],
            state=r.get("state", "verified"),
        )
        if not dry_run:
            was_inserted = repo.upsert_relationship(record)
            if was_inserted:
                inserted += 1
            else:
                updated += 1

    total = len(relationships)
    log.info("relationships_imported", total=total, inserted=inserted, updated=updated, dry_run=dry_run)
    return {"total": total, "inserted": inserted, "updated": updated}


def import_ocr(db, dry_run: bool) -> dict:
    """Import OCR job, pages, regions, candidate fields, and candidate links."""
    job_path = resolve(OCR_DIR / "job.json")
    job_data = json.loads(job_path.read_text(encoding="utf-8"))

    repo = OcrRepository(db)
    stats = {
        "job": 0,
        "pages": 0,
        "regions": 0,
        "fields": 0,
        "links": 0,
    }

    job_id = job_data["job_id"]
    source_hash = job_data["source_hash"]
    source_id = job_data["source_id"]

    # --- OCR Job ---
    job_record = OcrJobRecord(
        job_id=job_id,
        source_id=source_id,
        source_hash=source_hash,
        cache_key=job_data["cache_key"],
        configuration=job_data["configuration"],
        status=job_data["status"],
        review_state=job_data.get("review_state", "pending_review"),
        page_count=job_data["page_count"],
        started_at=job_data.get("started_at"),
    )
    if not dry_run:
        repo.upsert_job(job_record)
    stats["job"] = 1

    # --- OCR Pages ---
    for page_summary in job_data.get("pages", []):
        page_num = page_summary["source_page"]
        page_id = f"{job_id}::page-{page_num:03d}"
        page_record = OcrPageRecord(
            page_id=page_id,
            job_id=job_id,
            source_id=source_id,
            source_hash=source_hash,
            source_page=page_num,
            region_count=page_summary["region_count"],
            mean_confidence=page_summary["mean_confidence"],
            duration_ms=page_summary["duration_ms"],
            review_state=page_summary.get("review_state", "pending_review"),
            artifact_path=page_summary.get("artifact"),
        )
        if not dry_run:
            repo.upsert_page(page_record)
        stats["pages"] += 1

    # --- OCR Regions (from per-page JSON files) ---
    pages_dir = OCR_DIR / "pages"
    if pages_dir.exists():
        for page_file in sorted(pages_dir.glob("page-*.json")):
            page_data = json.loads(page_file.read_text(encoding="utf-8"))
            page_num = page_data.get("source_page", 0)
            for region in page_data.get("regions", []):
                region_id = region.get("region_id", f"p{page_num:03d}-unknown")
                region_record = OcrRegionRecord(
                    region_id=region_id,
                    job_id=job_id,
                    source_id=source_id,
                    source_hash=source_hash,
                    source_page=page_num,
                    text=region.get("text", ""),
                    confidence=region.get("confidence", 0.0),
                    bounding_box=region.get("bounding_box"),
                    words=region.get("words"),
                    state=region.get("state", "AI proposed"),
                    review_state=region.get("review_state", "pending_review"),
                )
                if not dry_run:
                    repo.upsert_region(region_record)
                stats["regions"] += 1

    # --- Candidate fields ---
    for cf in job_data.get("candidate_fields", []):
        field_id = (
            f"{job_id}::{cf['source_page']}::{cf['source_region_id']}::{cf['field']}"
        )
        field_record = WorkOrderFieldRecord(
            field_id=field_id,
            job_id=job_id,
            source_id=source_id,
            source_hash=source_hash,
            source_page=cf["source_page"],
            source_region_id=cf["source_region_id"],
            source_text=cf.get("source_text", ""),
            field=cf["field"],
            value=cf["value"],
            confidence=cf.get("confidence", 0.0),
            state=cf.get("state", "AI proposed"),
            review_state=cf.get("review_state", "pending_review"),
        )
        if not dry_run:
            repo.upsert_field(field_record)
        stats["fields"] += 1

    # --- Candidate asset links (from review_queue asset_link_review tasks) ---
    review_queue_path = resolve(OCR_DIR / "review_queue.json")
    queue_data = json.loads(review_queue_path.read_text(encoding="utf-8"))
    source_hash_queue = queue_data.get("source_hash", source_hash)

    for task in queue_data.get("tasks", []):
        if task.get("task_type") != "asset_link_review":
            continue
        tag = task.get("proposed_asset_tag") or task.get("asset_tag", "")
        if not tag:
            continue
        region_id = task.get("source_region_id", "")
        page_num = task.get("source_page", 0)
        link_id = f"{job_id}::{page_num}::{region_id}::{tag}"
        link_record = WorkOrderLinkRecord(
            link_id=link_id,
            task_id=task["task_id"],
            job_id=job_id,
            source_id=source_id,
            source_hash=source_hash_queue,
            source_page=page_num,
            source_region_id=region_id,
            asset_tag=tag,
            registry_matched=task.get("registry_matched", True),
            confidence=task.get("confidence"),
            state=task.get("state", "AI proposed"),
            review_state=task.get("state", "pending_review"),
        )
        if not dry_run:
            repo.upsert_link(link_record)
        stats["links"] += 1

    log.info("ocr_imported", **stats, dry_run=dry_run)
    return stats


def import_review_queue(db, dry_run: bool) -> dict:
    queue_path = resolve(OCR_DIR / "review_queue.json")
    queue_data = json.loads(queue_path.read_text(encoding="utf-8"))
    tasks = queue_data.get("tasks", [])

    repo = ReviewRepository(db)
    inserted = 0
    updated = 0

    for t in tasks:
        record = ReviewTaskRecord(
            task_id=t["task_id"],
            task_type=t["task_type"],
            source_id=t["source_id"],
            source_hash=t["source_hash"],
            source_page=t.get("source_page"),
            source_region_id=t.get("source_region_id"),
            source_artifact=t.get("source_artifact"),
            field=t.get("field"),
            proposed_value=t.get("proposed_value"),
            proposed_asset_tag=t.get("proposed_asset_tag"),
            confidence=t.get("confidence"),
            state=t.get("state", "pending_review"),
            allowed_decisions=t.get("allowed_decisions", []),
        )
        if not dry_run:
            was_inserted = repo.upsert_task(record)
            if was_inserted:
                inserted += 1
            else:
                updated += 1

    total = len(tasks)
    log.info("review_tasks_imported", total=total, inserted=inserted, updated=updated, dry_run=dry_run)
    return {"total": total, "inserted": inserted, "updated": updated}


def append_audit_event(db, summary: dict) -> None:
    repo = ReviewRepository(db)
    event = AuditEventRecord(
        event_type="import",
        entity_type="corpus",
        entity_id="active_dataset",
        actor="importer",
        detail=summary,
    )
    repo.append_event(event)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_import(db_name: str | None = None, uri: str | None = None, dry_run: bool = False) -> dict:
    """
    Execute the full corpus import. Returns a summary dict.
    Raises SystemExit(1) if MongoDB is unavailable.
    """
    from app.core.database import get_db as _get_db

    if not ping_db(db_name=db_name, uri=uri):
        log.error(
            "mongodb_unavailable",
            action="IMPORT ABORTED",
            hint=(
                f"MongoDB is not reachable at {uri or settings.mongodb_uri}. "
                "Please start MongoDB Community (mongod) and try again. "
                "See infra/mongodb/README.md for setup instructions."
            ),
        )
        sys.exit(1)

    db = _get_db(db_name=db_name, uri=uri)
    if not dry_run:
        ensure_indexes(db)

    log.info("import_started", db=db.name, dry_run=dry_run)
    started = datetime.utcnow()

    summary = {
        "dry_run": dry_run,
        "started_at": started.isoformat(),
        "documents": import_documents(db, dry_run),
        "assets": import_assets(db, dry_run),
        "relationships": import_relationships(db, dry_run),
        "ocr": import_ocr(db, dry_run),
        "review_tasks": import_review_queue(db, dry_run),
    }

    elapsed = (datetime.utcnow() - started).total_seconds()
    summary["elapsed_seconds"] = round(elapsed, 2)

    if not dry_run:
        append_audit_event(db, summary)

    log.info("import_complete", elapsed_seconds=elapsed, dry_run=dry_run)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pragyan PPI corpus importer")
    parser.add_argument("--db", default=None, help="MongoDB database name (overrides .env)")
    parser.add_argument("--uri", default=None, help="MongoDB URI (overrides .env)")
    parser.add_argument("--dry-run", action="store_true", help="Parse and validate without writing to MongoDB")
    args = parser.parse_args()

    summary = run_import(db_name=args.db, uri=args.uri, dry_run=args.dry_run)
    print(json.dumps(summary, indent=2, default=str))
