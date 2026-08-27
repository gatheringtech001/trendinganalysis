from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image

from report_pdf_editorial import EditorialDeck, PAGE
from report_pdf_pages import REFERENCE_SEQUENCE, SECTION_PAGE_ORDER
from visual_reports import FINAL_REPORT_NAME, PDF_NAME, REPORT_ID, SOURCE_NOTES_NAME


REFERENCE_SHA256 = "33dcf787c9fb88ecdcd2af95add94610755b3c7aae336a21b7db4712cfcec253"
LAYOUT_VERSION = "reference-53-page-v2"


def _shared_cached_image(image, shared_cache_dir):
    source_url = image.get("source_url")
    store_id = image.get("store_id")
    if not source_url or not store_id or not shared_cache_dir:
        return None
    cache_key = hashlib.sha256(f"{store_id}\0{source_url}".encode()).hexdigest()
    metadata_path = Path(shared_cache_dir) / f"{cache_key}.json"
    if not metadata_path.is_file():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        file_name = metadata["file"]
        if Path(file_name).name != file_name:
            return None
        path = metadata_path.parent / file_name
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != metadata["sha256"] or digest != image.get("sha256"):
            return None
        if len(data) != metadata["bytes"] or len(data) > 15_000_000:
            return None
        with Image.open(io.BytesIO(data)) as cached:
            cached.verify()
        return path
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _fetch_image(image, cache_dir, shared_cache_dir=None):
    shared = _shared_cached_image(image, shared_cache_dir)
    if shared is not None:
        return shared
    url = image["resolved_url"]
    parsed = urlparse(str(url))
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("证据图片URL必须使用HTTP或HTTPS")
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{hashlib.sha256(url.encode()).hexdigest()}.jpg"
    if path.is_file():
        return path
    request = urllib.request.Request(url, headers={"User-Agent": "FashionScope/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(15_000_001)
    if len(data) > 15_000_000:
        raise ValueError("证据图片超过15MB限制")
    with Image.open(io.BytesIO(data)) as image:
        image.convert("RGB").save(path, "JPEG", quality=90)
    return path


def _approval_summary(report):
    review = report["approved_analysis"]["review"]
    return f"报告专项分析 · {review['approved_sections']}/{review['total_sections']} 章节通过"


def _render(report, pdf_path, cache_dir, progress):
    images = {row["image_id"]: row for row in report["images"]}
    analysis_root = Path(os.environ.get(
        "FASHION_SCOPE_REPORT_ANALYSIS_OUTPUT_DIR",
        Path(__file__).with_name("runtime") / "report_analysis_jobs",
    ))
    shared_cache_dir = analysis_root / "_image_cache"
    deck = EditorialDeck(
        pdf_path, images,
        lambda image: _fetch_image(image, cache_dir, shared_cache_dir),
    )
    progress("rendering_cover", 10)
    deck.render(report)
    progress("rendering_sections", 85)
    deck.save()
    displayed = sorted(set(deck.displayed_evidence_ids))
    if not displayed:
        raise RuntimeError("PDF未展示任何结论证据图")
    return deck, displayed


def _final_payload(report, generated, pages):
    return {
        "report_id": REPORT_ID,
        "report_type": "final_visual",
        "title": "Aloruh 店铺视觉诊断",
        "generated_at": generated,
        "pages": pages,
        "sample_count": report["scope"]["target_images"],
        "summary": report["executive_summary"],
        "scope": report["scope"],
        "sections": report["sections"],
        "images": report["images"],
        "image_observations": report.get("image_observations", []),
        "approved_analysis": report["approved_analysis"],
    }


def _layout_contract(displayed_ids, page_placements):
    return {
        "version": LAYOUT_VERSION,
        "reference_sha256": REFERENCE_SHA256,
        "reference_pages": 53,
        "reference_page_size": list(PAGE),
        "design_language": "53-page black-white image-led reference sequence",
        "claim_layout": "reference conclusion presentation with store profile, full category distribution, reproducible key-category samples, and visible-only model observations",
        "page_sequence": [
            {
                "page": spec["page"], "kind": spec["kind"],
                "section": spec.get("section"), "title": spec["title"],
            }
            for spec in REFERENCE_SEQUENCE
        ],
        "section_page_order": [list(item) for item in SECTION_PAGE_ORDER],
        "displayed_evidence_image_ids": displayed_ids,
        "page_placements": page_placements,
        "raw_observation_index": False,
    }


def build_visual_report(report, output_dir, progress=lambda _stage, _value: None):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_dir) as temporary_name:
        temporary = Path(temporary_name)
        pdf_path = temporary / PDF_NAME
        deck, displayed_ids = _render(
            report, pdf_path, output_dir / "image_cache", progress,
        )
        generated = datetime.now(timezone.utc).isoformat()
        final = _final_payload(report, generated, deck.page)
        notes = {
            **final,
            "image_failures": [],
            "layout_contract": _layout_contract(displayed_ids, deck.page_placements),
            "usage": {
                "total_tokens": 0,
                "estimated_cost_usd": 0,
                "note": "最终PDF仅做本地排版，未调用模型",
            },
        }
        (temporary / SOURCE_NOTES_NAME).write_text(
            json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        (temporary / FINAL_REPORT_NAME).write_text(
            json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        progress("publishing", 95)
        os.replace(pdf_path, output_dir / PDF_NAME)
        os.replace(temporary / SOURCE_NOTES_NAME, output_dir / SOURCE_NOTES_NAME)
        os.replace(temporary / FINAL_REPORT_NAME, output_dir / FINAL_REPORT_NAME)
    progress("complete", 100)
    return {
        "report_id": REPORT_ID,
        "generated_at": generated,
        "pages": deck.page,
        "sample_count": report["scope"]["target_images"],
        "analysis_job_id": report["approved_analysis"]["job_id"],
        "usage": notes["usage"],
        "image_failures": [],
    }
