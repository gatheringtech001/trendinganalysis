from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from analysis_usage import AnalysisUsageRecorder, SOL_STANDARD_PRICING
from azure_openai_fashion_analyzer import AzureOpenAIOptions
from detailed_visual_analysis import AzureOpenAIDetailedAnalyzer, DetailedVisualItem
from fashion_image_analysis import DIMENSIONS, TAXONOMY
from high_resolution_images import download_high_resolution_image


DEFAULT_DB = Path(__file__).parents[2] / "2026-08-14" / "explorer" / "explorer.db"
DEFAULT_OUTPUT_ROOT = Path(__file__).parents[2] / "2026-08-19" / "detailed_visual"


def _read_filters(value: str) -> dict[str, str]:
    try:
        filters = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("filters must be valid JSON") from error
    if not isinstance(filters, dict) or not filters:
        raise ValueError("filters must be a non-empty JSON object")
    for dimension, tag in filters.items():
        if dimension not in DIMENSIONS:
            raise ValueError(f"unknown dimension: {dimension}")
        if tag not in TAXONOMY[dimension]:
            raise ValueError(f"unknown tag for {dimension}: {tag}")
    return filters


def _matches(tags: dict, filters: dict[str, str]) -> bool:
    return all(tag in tags.get(dimension, []) for dimension, tag in filters.items())


def select_images(
    db_path: Path, stores: list[str], filters: dict[str, str],
    images_per_store: int, max_images: int,
) -> list[dict]:
    connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro&immutable=1", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        known = {row[0] for row in connection.execute("SELECT DISTINCT store_id FROM images")}
        if not stores or len(stores) != len(set(stores)) or any(store not in known for store in stores):
            raise ValueError("stores must be unique known store IDs")
        placeholders = ",".join("?" for _ in stores)
        query = (
            "SELECT i.store_id, i.product_id, i.position, i.source_url, p.title, p.category, "
            "ia.tags_json FROM image_analysis ia JOIN images i USING(store_id, product_id, position) "
            "JOIN products p USING(store_id, product_id) "
            f"WHERE i.store_id IN ({placeholders}) ORDER BY i.store_id, p.catalog_rank, i.position"
        )
        grouped = {store: [] for store in stores}
        seen_urls = set()
        for row in connection.execute(query, stores):
            tags = json.loads(row["tags_json"])
            if not _matches(tags, filters) or row["source_url"] in seen_urls:
                continue
            grouped[row["store_id"]].append(dict(row))
            seen_urls.add(row["source_url"])
    finally:
        connection.close()
    sampler = random.SystemRandom()
    for rows in grouped.values():
        sampler.shuffle(rows)
    selected = []
    for index in range(images_per_store):
        for store in stores:
            if index < len(grouped[store]) and len(selected) < max_images:
                selected.append(grouped[store][index])
    if not selected:
        raise ValueError("no analyzed images match the fixed filter combination")
    return selected


def select_images_by_keys(
    db_path: Path, stores: list[str], filters: dict[str, str], selected_images: list[dict],
) -> list[dict]:
    requested = [
        (item["store_id"], item["product_id"], item["position"])
        for item in selected_images
    ]
    requested_set = set(requested)
    if (not requested or len(requested) != len(requested_set)
            or any(store_id not in stores for store_id, _, _ in requested)):
        raise ValueError("manual image selection is invalid")
    connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro&immutable=1", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" for _ in stores)
        query = (
            "SELECT i.store_id, i.product_id, i.position, i.source_url, p.title, p.category, "
            "ia.tags_json FROM image_analysis ia JOIN images i USING(store_id, product_id, position) "
            "JOIN products p USING(store_id, product_id) "
            f"WHERE i.store_id IN ({placeholders})"
        )
        rows_by_key = {}
        for row in connection.execute(query, stores):
            key = (row["store_id"], row["product_id"], row["position"])
            if key in requested_set:
                rows_by_key[key] = dict(row)
    finally:
        connection.close()
    missing = [key for key in requested if key not in rows_by_key]
    mismatched = [
        key for key in requested
        if key in rows_by_key and not _matches(json.loads(rows_by_key[key]["tags_json"]), filters)
    ]
    if missing:
        raise ValueError("a manually selected image was not found")
    if mismatched:
        raise ValueError("a manually selected image does not match the fixed filters")
    return [rows_by_key[key] for key in requested]


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    building = path.with_suffix(path.suffix + ".building")
    building.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(building, path)


def _run_dir(root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return root / stamp


def run(args) -> Path:
    filters = _read_filters(args.filters)
    stores = [value.strip() for value in args.stores.split(",") if value.strip()]
    selected_images = json.loads(args.selected_images) if args.selected_images else None
    if selected_images:
        rows = select_images_by_keys(args.db, stores, filters, selected_images)
    else:
        candidate_count = min(max(args.images_per_store * 8, 12), 32)
        candidate_limit = min(max(args.max_images * 8, len(stores) * 12), 160)
        rows = select_images(args.db, stores, filters, candidate_count, candidate_limit)
    output = args.output or _run_dir(args.output_root)
    image_dir = output / "images"
    downloads = []
    failures = []
    detailed_items = []
    completed_by_store = {store: 0 for store in stores}
    attempted_downloads = 0
    for row in rows:
        if len(detailed_items) >= args.max_images:
            break
        if not selected_images and completed_by_store[row["store_id"]] >= args.images_per_store:
            continue
        attempted_downloads += 1
        try:
            image = download_high_resolution_image(
                store_id=row["store_id"], product_id=row["product_id"],
                position=row["position"], source_url=row["source_url"],
                output_dir=image_dir, timeout=args.download_timeout,
            )
            downloads.append(image.to_dict())
            detailed_items.append(DetailedVisualItem(image, row["title"], row["category"]))
            completed_by_store[row["store_id"]] += 1
        except Exception as error:
            failures.append({"store_id": row["store_id"], "product_id": row["product_id"], "error": str(error)})
    manifest = {
        "status": "downloaded" if detailed_items else "failed",
        "filters": filters, "stores": stores,
        "selection_mode": "manual" if selected_images else "random",
        "requested_images_per_store": args.images_per_store,
        "candidate_images": len(rows), "attempted_downloads": attempted_downloads,
        "downloaded_images": len(detailed_items), "download_failures": failures,
        "model": args.deployment, "image_detail": "high",
        "hd_threshold": {"pixels": 800_000, "long_edge": 1_000, "short_edge": 600},
        "images": downloads,
    }
    _write_json(output / "manifest.json", manifest)
    if not detailed_items:
        raise RuntimeError("all HD image downloads failed")
    if args.dry_run:
        return output
    if not args.endpoint or not args.api_key:
        raise ValueError("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY are required")
    usage = AnalysisUsageRecorder(
        output / "usage.jsonl", output / "usage-summary.json",
        total_images=len(detailed_items), deployment=args.deployment,
        pricing=SOL_STANDARD_PRICING,
    )
    analyzer = AzureOpenAIDetailedAnalyzer(
        AzureOpenAIOptions(args.endpoint, args.api_key, args.deployment), usage.record,
    )
    try:
        analysis = analyzer.analyze(detailed_items, filters)
    except Exception:
        usage.finish("failed", completed_images=0)
        raise
    usage.finish("complete", completed_images=len(detailed_items))
    manifest.update(status="complete", analysis=analysis)
    _write_json(output / "result.json", manifest)
    return output


def parse_args():
    parser = argparse.ArgumentParser(description="HD cross-store visual analysis for a fixed dimension selection")
    parser.add_argument("--filters", required=True, help='JSON, e.g. {"product_category":"TOPS"}')
    parser.add_argument("--stores", required=True, help="Comma-separated store IDs")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--images-per-store", type=int, default=4, choices=range(1, 9))
    parser.add_argument("--max-images", type=int, default=16, choices=range(1, 25))
    parser.add_argument("--selected-images", help="JSON array of selected image identifiers")
    parser.add_argument("--download-timeout", type=int, default=30)
    parser.add_argument("--deployment", default="gpt-5.6-sol")
    parser.add_argument("--endpoint", default=os.environ.get("AZURE_OPENAI_ENDPOINT"))
    parser.add_argument("--api-key", default=os.environ.get("AZURE_OPENAI_KEY"))
    parser.add_argument("--dry-run", action="store_true", help="Download and validate HD images without calling Sol")
    return parser.parse_args()


if __name__ == "__main__":
    print(run(parse_args()))
