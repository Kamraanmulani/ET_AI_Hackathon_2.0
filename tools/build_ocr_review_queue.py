"""Create review tasks from a completed work-order OCR job without altering its evidence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JOB_PATH = ROOT / "Data" / "derived" / "ocr" / "work-orders-001" / "job.json"
OUTPUT_PATH = JOB_PATH.with_name("review_queue.json")


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def main() -> None:
    job = json.loads(JOB_PATH.read_text(encoding="utf-8"))
    if job.get("status") != "completed":
        raise RuntimeError("A completed OCR job is required before review tasks can be created.")

    tasks = []
    for page in job["pages"]:
        tasks.append({
            "task_id": f"ocr-page-{page['source_page']:03d}",
            "task_type": "ocr_page_review",
            "source_id": job["source_id"],
            "source_hash": job["source_hash"],
            "source_page": page["source_page"],
            "source_artifact": page["artifact"],
            "state": "pending_review",
            "allowed_decisions": ["verify_transcript", "correct_transcript", "mark_unreadable"],
        })

    for index, candidate in enumerate(job["candidate_fields"], start=1):
        if candidate["field"] == "asset_tag":
            continue
        tasks.append({
            "task_id": f"ocr-field-{index:03d}",
            "task_type": "ocr_field_review",
            "field": candidate["field"],
            "proposed_value": candidate["value"],
            "source_id": job["source_id"],
            "source_hash": job["source_hash"],
            "source_page": candidate["source_page"],
            "source_region_id": candidate["source_region_id"],
            "source_text": candidate["source_text"],
            "confidence": candidate["confidence"],
            "state": "pending_review",
            "allowed_decisions": ["verify", "correct", "reject", "mark_unreadable"],
        })

    for index, candidate in enumerate(job["candidate_asset_links"], start=1):
        tasks.append({
            "task_id": f"asset-link-{index:03d}",
            "task_type": "asset_link_review",
            "proposed_asset_tag": candidate["asset_tag"],
            "source_id": job["source_id"],
            "source_hash": job["source_hash"],
            "source_page": candidate["source_page"],
            "source_region_id": candidate["source_region_id"],
            "confidence": candidate["confidence"],
            "state": "pending_review",
            "allowed_decisions": ["approve_link", "correct_tag", "reject_link"],
        })

    payload = {
        "queue_id": f"review-{job['job_id']}",
        "source_job_id": job["job_id"],
        "source_hash": job["source_hash"],
        "generated_at": datetime.now(UTC).isoformat(),
        "state": "pending_review",
        "policy": "A reviewer decision is required before any field or asset link becomes verified evidence.",
        "task_count": len(tasks),
        "tasks": tasks,
    }
    write_json(OUTPUT_PATH, payload)
    print(json.dumps({"status": "created", "task_count": len(tasks), "path": str(OUTPUT_PATH)}))


if __name__ == "__main__":
    main()
