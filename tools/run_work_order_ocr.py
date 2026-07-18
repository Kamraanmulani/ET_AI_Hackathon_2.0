"""Run a local, reviewable PaddleOCR baseline for the supplied work-order PDF."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# PaddleOCR 3.x selects oneDNN on CPU by default. This Windows environment
# requires the regular Paddle backend; setting it before importing PaddleOCR
# keeps inference deterministic and avoids the incompatible oneDNN path.
os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "False")
os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(ROOT / ".paddle-cache"))

import fitz
import paddle
import paddleocr
from paddleocr import PaddleOCR


DEFAULT_OUTPUT = ROOT / "Data" / "derived" / "ocr" / "work-orders-001"
WORK_ORDER_PATTERN = re.compile(r"\bWO-\d{4}-\d{4}\b", re.IGNORECASE)
DATE_PATTERN = re.compile(r"\b(?:\d{1,2}|O\d)-[A-Za-z]{3}-\d{4}\b")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def polygon_to_list(polygon: Any) -> list[list[int]]:
    return [[int(point[0]), int(point[1])] for point in polygon]


def region_bounds(polygon: list[list[int]]) -> dict[str, int]:
    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    return {"x": min(xs), "y": min(ys), "width": max(xs) - min(xs), "height": max(ys) - min(ys)}


def find_candidate_fields(text: str, known_tags: list[str]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for work_order_id in WORK_ORDER_PATTERN.findall(text):
        candidates.append({"field": "work_order_id", "value": work_order_id.upper()})
    for candidate_date in DATE_PATTERN.findall(text):
        candidates.append({"field": "date_raw", "value": candidate_date})
    for tag in known_tags:
        if re.search(rf"(?<![A-Z0-9]){re.escape(tag)}(?![A-Z0-9])", text, re.IGNORECASE):
            candidates.append({"field": "asset_tag", "value": tag})
    return candidates


def load_source_context() -> tuple[Path, str, list[str]]:
    manifest_path = ROOT / "Data" / "manifests" / "source_manifest.json"
    registry_path = ROOT / "Data" / "manifests" / "pid_asset_registry.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source = next(item for item in manifest["sources"] if item["source_id"] == "work-orders-001")
    source_path = ROOT / source["path"]
    if not source_path.is_file():
        raise FileNotFoundError(f"Required source file is unavailable: {source_path}")
    tags = sorted((asset["tag"] for asset in json.loads(registry_path.read_text(encoding="utf-8"))["assets"]), key=len, reverse=True)
    return source_path, source["sha256"], tags


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Directory for derived OCR artifacts.")
    parser.add_argument("--render-scale", type=float, default=2.0, help="PyMuPDF rendering scale; 2.0 is the baseline.")
    parser.add_argument("--force", action="store_true", help="Ignore a matching completed cache entry.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_path, expected_hash, known_tags = load_source_context()
    source_hash = sha256_file(source_path)
    if source_hash != expected_hash:
        raise RuntimeError("Source hash differs from source_manifest.json; OCR is stopped to preserve provenance.")

    config = {
        "engine": "PaddleOCR",
        "paddleocr_version": paddleocr.__version__,
        "paddle_version": paddle.__version__,
        "language": "en",
        "device": "cpu",
        "paddlex_enable_mkldnn_bydefault": False,
        "render_scale": args.render_scale,
        "document_orientation": False,
        "document_unwarping": False,
        "textline_orientation": False,
        "return_word_box": True,
    }
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    output_dir = args.output.resolve()
    job_path = output_dir / "job.json"
    if job_path.is_file() and not args.force:
        existing = json.loads(job_path.read_text(encoding="utf-8"))
        if existing.get("source_hash") == source_hash and existing.get("configuration_hash") == config_hash and existing.get("status") == "completed":
            print(json.dumps({"status": "cache_hit", "job_path": str(job_path), "cache_key": existing["cache_key"]}))
            return 0

    started = time.perf_counter()
    cache_key = f"{source_hash[:16]}-{config_hash}"
    pages_dir = output_dir / "pages"
    page_images_dir = output_dir / "page_images"
    job: dict[str, Any] = {
        "job_id": f"ocr-{cache_key}",
        "source_id": "work-orders-001",
        "source_path": str(source_path.relative_to(ROOT)).replace("\\", "/"),
        "source_hash": source_hash,
        "cache_key": cache_key,
        "configuration_hash": config_hash,
        "configuration": config,
        "status": "running",
        "review_state": "pending_review",
        "started_at": datetime.now(UTC).isoformat(),
        "page_count": 0,
        "pages": [],
        "candidate_fields": [],
        "candidate_asset_links": [],
        "notes": [
            "All OCR text, field candidates, and asset links are AI proposed until human review.",
            "No diagnosis, root-cause conclusion, maintenance action, or source-normalised date is created by this baseline.",
        ],
    }
    write_json(job_path, job)

    try:
        document = fitz.open(source_path)
        job["page_count"] = len(document)
        engine = PaddleOCR(
            lang="en",
            device="cpu",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        for page_number, page in enumerate(document, start=1):
            page_started = time.perf_counter()
            image_path = page_images_dir / f"page-{page_number:03d}.png"
            image_path.parent.mkdir(parents=True, exist_ok=True)
            page.get_pixmap(matrix=fitz.Matrix(args.render_scale, args.render_scale), alpha=False).save(image_path)
            result = engine.predict(str(image_path), return_word_box=True)[0]
            texts = result.get("rec_texts", [])
            scores = result.get("rec_scores", [])
            polygons = result.get("rec_polys", [])
            regions: list[dict[str, Any]] = []
            for index, text in enumerate(texts, start=1):
                polygon = polygon_to_list(polygons[index - 1])
                region = {
                    "region_id": f"p{page_number:03d}-r{index:03d}",
                    "text": str(text),
                    "confidence": round(float(scores[index - 1]), 6),
                    "polygon": polygon,
                    "bounding_box": region_bounds(polygon),
                    "coordinate_space": "rendered_page_pixels",
                    "review_state": "pending_review",
                }
                regions.append(region)
                for field in find_candidate_fields(region["text"], known_tags):
                    candidate = {
                        "field": field["field"],
                        "value": field["value"],
                        "source_page": page_number,
                        "source_region_id": region["region_id"],
                        "source_text": region["text"],
                        "confidence": region["confidence"],
                        "state": "AI proposed",
                        "review_state": "pending_review",
                    }
                    job["candidate_fields"].append(candidate)
                    if field["field"] == "asset_tag":
                        job["candidate_asset_links"].append({
                            "asset_tag": field["value"],
                            "source_page": page_number,
                            "source_region_id": region["region_id"],
                            "confidence": region["confidence"],
                            "state": "AI proposed",
                            "review_state": "pending_review",
                        })
            page_data = {
                "source_page": page_number,
                "rendered_image": str(image_path.relative_to(output_dir)).replace("\\", "/"),
                "render_scale": args.render_scale,
                "raw_text": "\n".join(str(text) for text in texts),
                "regions": regions,
                "region_count": len(regions),
                "mean_confidence": round(sum(float(score) for score in scores) / len(scores), 6) if scores else None,
                "duration_ms": round((time.perf_counter() - page_started) * 1000, 2),
                "review_state": "pending_review" if regions else "unreadable",
            }
            page_path = pages_dir / f"page-{page_number:03d}.json"
            write_json(page_path, page_data)
            job["pages"].append({
                "source_page": page_number,
                "artifact": str(page_path.relative_to(output_dir)).replace("\\", "/"),
                "review_state": page_data["review_state"],
                "region_count": page_data["region_count"],
                "mean_confidence": page_data["mean_confidence"],
                "duration_ms": page_data["duration_ms"],
            })
        document.close()
        job["status"] = "completed"
        job["finished_at"] = datetime.now(UTC).isoformat()
        job["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
        write_json(job_path, job)
        print(json.dumps({"status": job["status"], "job_path": str(job_path), "cache_key": cache_key, "duration_ms": job["duration_ms"]}))
        return 0
    except Exception as error:
        job["status"] = "failed"
        job["finished_at"] = datetime.now(UTC).isoformat()
        job["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
        job["error"] = {"stage": "ocr_baseline", "type": type(error).__name__, "message": str(error)}
        write_json(job_path, job)
        raise


if __name__ == "__main__":
    sys.exit(main())
