from __future__ import annotations

import argparse
import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from analysis_usage import AnalysisUsageRecorder, pricing_for_deployment
from azure_openai_fashion_analyzer import (
    AzureOpenAIOptions,
    AzureOpenAIFashionAnalyzer,
    image_data_url,
)
from fashion_image_analysis import (
    ANALYSIS_VERSION,
    AnalysisRunOptions,
    DIMENSIONS,
    ImageAnalysisRequest,
    analyze_incremental,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "app" / "explorer.db"
DEFAULT_DATA = PROJECT_ROOT / "data"
STORE_FILES = {
    "motel": "images_motel.jsonl",
    "princess_polly": "images_princess_polly.jsonl",
    "prettylittlething": "images_prettylittlething.jsonl",
    "aloruh_local": "images_aloruh_customer.jsonl",
    "aloruh_shein": "images_aloruh_shein.jsonl",
}
DEFAULT_STORES = tuple(STORE_FILES)


@dataclass(frozen=True)
class Target:
    store_id: str
    product_id: str
    position: int


@dataclass(frozen=True)
class PendingAnalysis:
    requests: list[ImageAnalysisRequest]
    targets_by_key: dict[str, list[Target]]


def load_pending(
    db_path: Path, store_id: str, category_group: str | None, position: int,
) -> PendingAnalysis:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    category_filter = "AND p.category_group = ?" if category_group else ""
    parameters = [store_id]
    if category_group:
        parameters.append(category_group)
    parameters.extend([position, ANALYSIS_VERSION])
    rows = connection.execute(f"""
        SELECT p.store_id, p.product_id, p.title, p.category, i.position, i.source_url
        FROM products p
        JOIN images i USING(store_id, product_id)
        LEFT JOIN image_analysis a USING(store_id, product_id, position)
        WHERE p.store_id = ? {category_filter} AND i.position = ?
          AND (a.product_id IS NULL OR a.analysis_version != ?)
        ORDER BY p.product_id
    """, parameters).fetchall()
    connection.close()

    rows_by_url: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        rows_by_url.setdefault(row["source_url"], []).append(row)
    requests = []
    targets_by_key = {}
    for index, same_image in enumerate(rows_by_url.values(), 1):
        row = same_image[0]
        scope = category_group or "ALL"
        key = f"{store_id}:{scope}:{position}:{index}"
        requests.append(ImageAnalysisRequest(
            key=key, image_url=row["source_url"], title=row["title"],
            current_category=row["category"], position=position,
        ))
        targets_by_key[key] = [
            Target(item["store_id"], item["product_id"], item["position"])
            for item in same_image
        ]
    return PendingAnalysis(requests, targets_by_key)


def _database_rows(target: Target, analysis: dict) -> tuple[tuple, list[tuple]]:
    key = (target.store_id, target.product_id, target.position)
    record = key + (
        analysis["analysis_version"], analysis["analysis_status"],
        analysis["analysis_method"], json.dumps(analysis["tags"], ensure_ascii=False),
        json.dumps(analysis["confidence"], ensure_ascii=False),
    )
    tags = [
        key + (dimension, tag, float(analysis["confidence"][dimension]))
        for dimension in DIMENSIONS for tag in analysis["tags"][dimension]
    ]
    return record, tags


def _persist_database(
    db_path: Path, targets_by_key: dict[str, list[Target]], results: dict[str, dict],
) -> None:
    connection = sqlite3.connect(db_path)
    try:
        with connection:
            for key, analysis in results.items():
                for target in targets_by_key[key]:
                    record, tags = _database_rows(target, analysis)
                    connection.execute(
                        "INSERT OR REPLACE INTO image_analysis VALUES(?,?,?,?,?,?,?,?)",
                        record,
                    )
                    connection.execute(
                        "DELETE FROM image_analysis_tags "
                        "WHERE store_id=? AND product_id=? AND position=?",
                        (target.store_id, target.product_id, target.position),
                    )
                    connection.executemany(
                        "INSERT INTO image_analysis_tags VALUES(?,?,?,?,?,?)", tags,
                    )
    finally:
        connection.close()


def _persist_jsonl(
    images_path: Path, targets_by_key: dict[str, list[Target]], results: dict[str, dict],
) -> None:
    analyses = {
        (target.product_id, target.position): results[key]
        for key, targets in targets_by_key.items() for target in targets
    }
    analyses_by_url = {}
    with images_path.open(encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            source_url = row.get("source_url")
            analysis = analyses.get(
                (str(row.get("product_id")), int(row.get("position") or 0)),
            ) or row.get("analysis")
            if analysis and source_url:
                analyses_by_url.setdefault(source_url, analysis)
    building = images_path.with_suffix(images_path.suffix + ".building")
    with images_path.open(encoding="utf-8") as source, building.open(
        "w", encoding="utf-8", newline="\n",
    ) as destination:
        for line in source:
            row = json.loads(line)
            analysis = analyses.get(
                (str(row.get("product_id")), int(row.get("position") or 0)),
            ) or analyses_by_url.get(row.get("source_url"))
            if analysis:
                row["analysis"] = analysis
            destination.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(building, images_path)


def persist_results(
    db_path: Path, images_path: Path, targets_by_key: dict[str, list[Target]],
    results: dict[str, dict],
) -> None:
    _persist_jsonl(images_path, targets_by_key, results)
    _persist_database(db_path, targets_by_key, results)


def _analyzer(args, usage_callback) -> AzureOpenAIFashionAnalyzer:
    options = AzureOpenAIOptions(
        endpoint=args.endpoint, credential=args.api_key,
        deployment=args.deployment, auth_type=args.auth_type,
    )
    return AzureOpenAIFashionAnalyzer(
        options, image_loader=image_data_url, usage_callback=usage_callback,
    )


def run_store(args, store_id: str) -> dict:
    pending = load_pending(args.db, store_id, args.category_group, args.position)
    unique_count = len(pending.requests)
    target_count = sum(len(targets) for targets in pending.targets_by_key.values())
    print(f"STORE {store_id}: pending={target_count} unique_urls={unique_count}", flush=True)
    if not unique_count:
        return {"store_id": store_id, "targets": 0, "unique_urls": 0}

    category_stem = args.category_group.lower() if args.category_group else "all"
    stem = f"image_analysis_{category_stem}_cover_{store_id}"
    output = args.data_dir / f"{stem}.jsonl"
    usage = AnalysisUsageRecorder(
        args.data_dir / f"{stem}.usage.jsonl",
        args.data_dir / f"{stem}.usage-summary.json",
        total_images=unique_count, deployment=args.deployment,
        pricing=pricing_for_deployment(args.deployment),
    )
    try:
        results = analyze_incremental(
            pending.requests, _analyzer(args, usage.record),
            AnalysisRunOptions(
                output, batch_size=args.batch_size, workers=args.workers,
                progress=lambda done, total: print(
                    f"PROGRESS {store_id}: {done}/{total}", flush=True,
                ),
            ),
        )
        persist_results(
            args.db, args.data_dir / STORE_FILES[store_id],
            pending.targets_by_key, results,
        )
    except BaseException:
        completed = sum(1 for line in output.with_suffix(
            output.suffix + ".partial"
        ).read_text(encoding="utf-8").splitlines() if line.strip()) if output.with_suffix(
            output.suffix + ".partial"
        ).exists() else 0
        usage.finish("failed", completed_images=completed)
        raise
    usage.finish("complete", completed_images=unique_count)
    print(f"COMPLETE {store_id}: {target_count} targets", flush=True)
    return {"store_id": store_id, "targets": target_count, "unique_urls": unique_count}


def parse_args():
    parser = argparse.ArgumentParser(description="Analyze selected Fashion Scope cover images")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--store", action="append", choices=STORE_FILES)
    category = parser.add_mutually_exclusive_group()
    category.add_argument("--category-group", default="SKIRTS")
    category.add_argument("--all-categories", action="store_true")
    parser.add_argument("--position", type=int, default=1)
    parser.add_argument("--deployment", default="gpt-5.6-terra")
    parser.add_argument("--endpoint", default=os.environ.get("AZURE_OPENAI_ENDPOINT"))
    parser.add_argument("--api-key", default=os.environ.get("AZURE_OPENAI_KEY"))
    parser.add_argument("--auth-type", choices=("api_key", "bearer"), default="api_key")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if args.all_categories:
        args.category_group = None
    args.store = args.store or list(DEFAULT_STORES)
    try:
        pricing_for_deployment(args.deployment)
    except ValueError as error:
        parser.error(str(error))
    if not args.endpoint or not args.api_key:
        parser.error("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY are required")
    return args


def main():
    args = parse_args()
    summary = [run_store(args, store_id) for store_id in args.store]
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
