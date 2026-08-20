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
from visual_reports import FINAL_REPORT_NAME, PDF_NAME, REPORT_ID, SOURCE_NOTES_NAME


REFERENCE_SHA256 = "33dcf787c9fb88ecdcd2af95add94610755b3c7aae336a21b7db4712cfcec253"
LAYOUT_VERSION = "editorial-image-first-v1"


def _fetch_image(url, cache_dir):
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


def _evidence_ids(report):
    ids = []
    for section in report["sections"]:
        for claim in section["claims"]:
            evidence = claim["evidence"]
            ids.extend(evidence["support_image_ids"])
            ids.extend(evidence["counterexample_image_ids"])
    return ids


def _render(report, pdf_path, cache_dir, progress):
    images = {row["image_id"]: row for row in report["images"]}
    deck = EditorialDeck(
        pdf_path, images,
        lambda url: _fetch_image(url, cache_dir),
    )
    progress("rendering_cover", 10)
    deck.cover()
    deck.executive(report)
    deck.scope(report)
    total_claims = sum(len(section["claims"]) for section in report["sections"])
    completed_claims = 0
    for section_index, section in enumerate(report["sections"], 1):
        deck.section_divider(section, section_index)
        for claim_index, claim in enumerate(section["claims"], 1):
            deck.claim(section, claim, claim_index)
            completed_claims += 1
            progress(
                "rendering_sections",
                20 + round(completed_claims / max(total_claims, 1) * 65),
            )
    deck.closing(report)
    deck.save()
    expected = set(_evidence_ids(report))
    displayed = set(deck.displayed_evidence_ids)
    if expected != displayed:
        missing = sorted(expected - displayed)
        raise RuntimeError(f"PDF未展示全部支持与反例图片: {missing[:10]}")
    return deck, sorted(displayed)


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


def _layout_contract(displayed_ids):
    return {
        "version": LAYOUT_VERSION,
        "reference_sha256": REFERENCE_SHA256,
        "reference_pages": 53,
        "reference_page_size": list(PAGE),
        "design_language": "black-white-sand editorial image-first",
        "claim_layout": "editorial hero followed by complete image evidence",
        "displayed_evidence_image_ids": displayed_ids,
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
            "layout_contract": _layout_contract(displayed_ids),
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
