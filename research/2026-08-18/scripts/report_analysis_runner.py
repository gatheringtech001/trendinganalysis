from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from analysis_usage import AnalysisUsageRecorder, SOL_STANDARD_PRICING
from azure_openai_fashion_analyzer import AzureOpenAIOptions
from high_resolution_images import download_high_resolution_image
from report_analysis_model import AzureOpenAIReportAnalyzer, SECTION_IDS


COMPETITOR_STORES = ("princess_polly", "motel", "prettylittlething")
BATCH_SIZE = 8


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    building = path.with_suffix(path.suffix + ".building")
    building.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    os.replace(building, path)


def _image_id(row: dict) -> str:
    key = f"{row['store_id']}:{row['product_id']}:{row['position']}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]


def _select_rows(
    db_path: Path, target_store: str, categories: list[str],
    competitor_sample_per_store: int,
) -> list[dict]:
    connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro&immutable=1", uri=True)
    connection.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in categories)
    query = (
        "SELECT i.store_id, i.product_id, i.position, i.source_url, p.title, "
        "p.category, p.category_group, p.catalog_rank FROM images i "
        "JOIN products p USING(store_id, product_id) WHERE i.position=1 "
        f"AND p.category_group IN ({placeholders}) AND i.store_id=? "
        "ORDER BY p.catalog_rank, p.product_id"
    )
    try:
        target = [dict(row) for row in connection.execute(query, [*categories, target_store])]
        competitors = []
        for store in COMPETITOR_STORES:
            rows = [dict(row) for row in connection.execute(query, [*categories, store])]
            competitors.extend(_spread_sample(rows, competitor_sample_per_store))
    finally:
        connection.close()
    seen = set()
    result = []
    for role, rows in (("target", target), ("competitor", competitors)):
        for row in rows:
            if row["source_url"] in seen:
                continue
            seen.add(row["source_url"])
            result.append({**row, "image_id": _image_id(row), "role": role})
    if not any(row["role"] == "target" for row in result):
        raise ValueError("report scope contains no target cover images")
    return result


def _spread_sample(rows: list[dict], count: int) -> list[dict]:
    if count <= 0 or not rows:
        return []
    if count == 1:
        return [rows[0]]
    if len(rows) <= count:
        return rows
    indexes = {round(index * (len(rows) - 1) / (count - 1)) for index in range(count)}
    return [rows[index] for index in sorted(indexes)]


def _public_image(item: dict) -> dict:
    download = item["download"].to_dict()
    download.pop("path", None)
    return {
        "image_id": item["image_id"], "role": item["role"],
        "store_id": item["store_id"], "product_id": item["product_id"],
        "category": item["category_group"], "title": item["title"], **download,
    }


def _compact_evidence(batch_results: list[dict]) -> dict:
    return {
        "observations": [
            row for batch in batch_results for row in batch["observations"]
        ],
        "pattern_candidates": [
            row for batch in batch_results for row in batch["pattern_candidates"]
        ],
    }


def _validate_claim_references(report: dict, known_ids: set[str]) -> None:
    for section in report["sections"]:
        for claim in section["claims"]:
            evidence = claim["evidence"]
            for field in (
                "support_image_ids", "counterexample_image_ids", "example_image_ids",
            ):
                unknown = set(evidence[field]) - known_ids
                if unknown:
                    raise ValueError(f"report claim references unknown images: {sorted(unknown)}")


def run_report_analysis(args, progress=lambda _stage, _value: None) -> Path:
    if not args.endpoint or not args.api_key:
        raise ValueError("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY are required")
    rows = _select_rows(
        args.db, args.target_store, args.categories, args.competitor_sample_per_store,
    )
    output = Path(args.output)
    progress("downloading_hd_images", 5)
    items, failures = [], []
    for index, row in enumerate(rows, 1):
        try:
            download = download_high_resolution_image(
                store_id=row["store_id"], product_id=row["product_id"],
                position=row["position"], source_url=row["source_url"],
                output_dir=output / "images", timeout=args.download_timeout,
            )
            items.append({**row, "download": download})
        except Exception as error:
            failures.append({
                "image_id": row["image_id"], "store_id": row["store_id"],
                "product_id": row["product_id"], "error": str(error)[:1000],
            })
        progress("downloading_hd_images", min(35, 5 + round(index / len(rows) * 30)))
    target_total = sum(item["role"] == "target" for item in items)
    if not target_total:
        raise RuntimeError("all target HD image downloads failed")
    scope = {
        "target_store": args.target_store, "categories": args.categories,
        "target_images": target_total,
        "competitor_images": sum(item["role"] == "competitor" for item in items),
        "competitor_sampling": f"每店最多{args.competitor_sample_per_store}张分位抽样",
        "position": 1, "excluded_metrics": ["曝光", "点击", "转化", "销量", "ROI"],
    }
    manifest = {
        "status": "analyzing", "scope": scope, "model": args.deployment,
        "image_detail": "high", "selected_images": len(rows),
        "downloaded_images": len(items), "download_failures": failures,
        "images": [_public_image(item) for item in items],
    }
    _write_json(output / "manifest.json", manifest)
    usage = AnalysisUsageRecorder(
        output / "usage.jsonl", output / "usage-summary.json",
        total_images=len(items), deployment=args.deployment, pricing=SOL_STANDARD_PRICING,
    )
    analyzer = AzureOpenAIReportAnalyzer(
        AzureOpenAIOptions(args.endpoint, args.api_key, args.deployment), usage.record,
    )
    batches = []
    try:
        for start in range(0, len(items), BATCH_SIZE):
            batch = items[start:start + BATCH_SIZE]
            batches.append(analyzer.analyze_images(batch))
            _write_json(output / "observations" / f"batch-{start // BATCH_SIZE + 1:04d}.json", batches[-1])
            progress(
                "analyzing_all_images",
                35 + round(min(start + BATCH_SIZE, len(items)) / len(items) * 45),
            )
        evidence = _compact_evidence(batches)
        _write_json(output / "image-observations.json", evidence)
        progress("synthesizing_report_sections", 85)
        report = analyzer.synthesize(evidence, scope)
        _validate_claim_references(report, {item["image_id"] for item in items})
    except Exception:
        usage.finish("failed", completed_images=sum(len(batch["observations"]) for batch in batches))
        raise
    usage.finish("complete", completed_images=len(items))
    result = {
        **manifest, "status": "complete", "executive_summary": report["executive_summary"],
        "sections": report["sections"], "image_observations": evidence["observations"],
        "analysis_contract": {
            "section_ids": list(SECTION_IDS),
            "claim_evidence_required": [
                "derivation", "support_image_ids", "counterexample_image_ids",
                "example_image_ids", "sample_count", "filters", "observation_fields",
            ],
        },
    }
    _write_json(output / "result.json", result)
    progress("report_analysis_complete", 100)
    return output


def revise_report_section(args, progress=lambda _stage, _value: None) -> Path:
    output = Path(args.output)
    result_path = output / "result.json"
    evidence_path = output / "image-observations.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    section = next(
        (row for row in result["sections"] if row["section_id"] == args.section_id), None,
    )
    if section is None:
        raise ValueError("unknown report section")
    usage = AnalysisUsageRecorder(
        output / "revision-usage.jsonl", output / "revision-usage-summary.json",
        total_images=len(result["images"]), deployment=args.deployment,
        pricing=SOL_STANDARD_PRICING,
    )
    analyzer = AzureOpenAIReportAnalyzer(
        AzureOpenAIOptions(args.endpoint, args.api_key, args.deployment), usage.record,
    )
    progress("revising_section", 40)
    try:
        revised = analyzer.revise(section, args.suggestion, evidence, result["scope"])
        _validate_claim_references(
            {"sections": [revised]}, {row["image_id"] for row in result["images"]},
        )
    except Exception:
        usage.finish("failed", completed_images=0)
        raise
    usage.finish("complete", completed_images=len(result["images"]))
    revised["revision"] = {
        "suggestion": args.suggestion,
        "revision_number": int((section.get("revision") or {}).get("revision_number", 0)) + 1,
    }
    result["sections"] = [
        revised if row["section_id"] == args.section_id else row
        for row in result["sections"]
    ]
    _write_json(result_path, result)
    progress("revision_complete", 100)
    return output


def default_args(**overrides):
    values = {
        "db": None, "output": None, "target_store": "aloruh_shein",
        "categories": ["TOPS", "SKIRTS"], "competitor_sample_per_store": 12,
        "download_timeout": 30, "deployment": "gpt-5.6-sol",
        "endpoint": os.environ.get("AZURE_OPENAI_ENDPOINT"),
        "api_key": os.environ.get("AZURE_OPENAI_KEY"),
    }
    values.update(overrides)
    return SimpleNamespace(**values)
