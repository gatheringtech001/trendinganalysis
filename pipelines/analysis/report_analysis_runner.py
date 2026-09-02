from __future__ import annotations

import hashlib
import json
import os
import random
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from types import SimpleNamespace

from analysis_usage import AnalysisUsageRecorder, pricing_for_deployment
from azure_openai_fashion_analyzer import AzureOpenAIOptions
from fashion_image_analysis import DIMENSIONS
from high_resolution_images import download_high_resolution_image
from report_analysis_model import AzureOpenAIReportAnalyzer, OBSERVABLE_FIELDS, SECTION_IDS


COMPETITOR_STORES = ("princess_polly", "motel", "prettylittlething")
COMPETITOR_BRANDS = {
    "princess_polly": "Princess Polly",
    "motel": "Motel Rocks",
    "prettylittlething": "PrettyLittleThing",
}
BATCH_SIZE = 8
REPORT_ANALYSIS_WORKERS = 4
SELECTION_DIMENSIONS = (
    "product_category", "silhouette_fit", "design_elements", "material_texture",
    "occasion", "color_pattern", "composition", "view_action", "selling_points",
    "scene", "visual_language", "styling",
)
SUPPLEMENTARY_CATEGORIES = (
    "T-SHIRTS", "SKIRTS", "TWO-PIECE SETS",
    "OUTERWEAR", "SUITS", "KNIT SETS",
)
SUPPLEMENTARY_SAMPLE_PER_CATEGORY = 5
TARGET_VIEW_LIMIT = 2
STORE_NAMES = {"aloruh_shein": "Aloruh(shein)", **COMPETITOR_BRANDS}


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    building = path.with_suffix(path.suffix + ".building")
    building.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    os.replace(building, path)


def _shared_image_cache(args, output: Path) -> Path:
    configured = getattr(args, "image_cache", None)
    return Path(configured) if configured else output.parent / "_image_cache"


def _image_id(row: dict) -> str:
    key = f"{row['store_id']}:{row['product_id']}:{row['position']}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]


def _select_rows(
    db_path: Path, target_store: str, categories: list[str] | None = None,
    key_category_limit: int = 3, sample_per_category: int = 20,
    sample_seed: str = "report-analysis",
) -> tuple[list[dict], dict]:
    connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro&immutable=1", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        distribution = _category_distribution(connection, target_store)
        selected_categories = categories or [
            row["category"] for row in distribution[:key_category_limit]
        ]
        if not selected_categories:
            raise ValueError("report scope contains no target categories")
        populations = {row["category"]: row["products"] for row in distribution}
        target, key_categories = _select_target_samples(
            connection, target_store, selected_categories,
            sample_per_category, sample_seed, populations,
            evidence_role="key_category_random_sample",
        )
        supplementary_names = [] if categories else [
            category for category in SUPPLEMENTARY_CATEGORIES
            if category in populations and category not in selected_categories
        ]
        supplementary, supplementary_categories = _select_target_samples(
            connection, target_store, supplementary_names,
            SUPPLEMENTARY_SAMPLE_PER_CATEGORY, sample_seed, populations,
            evidence_role="supplementary_category_random_sample",
        )
        target = _expand_target_views(
            connection, target_store, target + supplementary, TARGET_VIEW_LIMIT,
        )
        analysis_categories = selected_categories + supplementary_names
        target_plan = {
            "store_profile": _store_profile(connection, target_store),
            "distribution": distribution,
            "key_categories": key_categories,
            "supplementary_categories": supplementary_categories,
            "sampling": {
                "method": "deterministic_random", "seed": sample_seed,
                "sample_per_category": sample_per_category,
                "supplementary_sample_per_category": SUPPLEMENTARY_SAMPLE_PER_CATEGORY,
                "views_per_product": TARGET_VIEW_LIMIT,
            },
            "dimension_distributions": _store_dimension_distributions(
                connection, target_store, DIMENSIONS,
            ),
        }
        competitors, stores = [], {}
        for store in COMPETITOR_STORES:
            selected, plan = _select_store_evidence(
                connection, store, analysis_categories,
            )
            competitors.extend(selected)
            stores[store] = plan
    finally:
        connection.close()
    seen = set()
    result = []
    for role, rows in (("target", target), ("competitor", competitors)):
        for row in rows:
            if row["source_url"] in seen:
                continue
            seen.add(row["source_url"])
            reasons = row.get("selection_reasons") or [{"evidence_role": "unclassified"}]
            result.append({
                **row, "image_id": _image_id(row), "role": role,
                "selection_reasons": reasons,
            })
    if not any(row["role"] == "target" for row in result):
        raise ValueError("report scope contains no target cover images")
    return result, {
        "method": "dimension_stratified", "dimensions": list(SELECTION_DIMENSIONS),
        "target": target_plan, "categories": analysis_categories, "stores": stores,
    }


def _table_columns(connection, table: str) -> set[str]:
    return {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}


def _store_profile(connection, store: str) -> dict:
    columns = _table_columns(connection, "products")
    optional = [
        name for name in ("market", "channel", "source_type", "retrieved_at")
        if name in columns
    ]
    selects = ["COUNT(*) AS product_count"]
    for name in optional:
        aggregate = "MAX" if name == "retrieved_at" else "MIN"
        selects.append(f"{aggregate}({name}) AS {name}")
    row = dict(connection.execute(
        f"SELECT {', '.join(selects)} FROM products WHERE store_id=?", (store,),
    ).fetchone())
    image_count = connection.execute(
        "SELECT COUNT(*) FROM images WHERE store_id=?", (store,),
    ).fetchone()[0]
    category_count = connection.execute(
        "SELECT COUNT(DISTINCT category_group) FROM products WHERE store_id=?", (store,),
    ).fetchone()[0]
    return {
        "store_id": store, "store_name": STORE_NAMES.get(store, store),
        "platform": "SHEIN SG" if store == "aloruh_shein" else row.get("source_type"),
        "product_count": row["product_count"], "image_count": image_count,
        "category_count": category_count, "market": row.get("market"),
        "channel": row.get("channel"), "data_updated_at": row.get("retrieved_at"),
    }


def _category_distribution(connection, store: str) -> list[dict]:
    rows = [dict(row) for row in connection.execute(
        "SELECT category_group AS category, COUNT(*) AS products, "
        "MIN(COALESCE(catalog_rank, 999999999)) AS first_rank "
        "FROM products WHERE store_id=? GROUP BY category_group "
        "ORDER BY products DESC, first_rank, category_group", (store,),
    )]
    total = sum(row["products"] for row in rows)
    for row in rows:
        row.pop("first_rank", None)
        row["share"] = round(row["products"] / total, 4) if total else 0
    return rows


def _select_target_samples(
    connection, store: str, categories: list[str],
    sample_per_category: int, seed: str, populations: dict[str, int],
    evidence_role: str,
) -> tuple[list[dict], list[dict]]:
    selected, plans = [], []
    for category in categories:
        rows = _catalog_rows(connection, store, [category])
        rng = random.Random(f"{seed}:{category}")
        sampled = rng.sample(rows, min(sample_per_category, len(rows)))
        reason = {
            "evidence_role": evidence_role, "category": category,
            "population_products": populations.get(category, 0),
            "eligible_cover_images": len(rows), "seed": seed,
        }
        selected.extend({**row, "selection_reasons": [reason]} for row in sampled)
        plans.append({
            "category": category,
            "population_products": populations.get(category, 0),
            "eligible_cover_images": len(rows),
            "sample_selected": len(sampled),
        })
    return selected, plans


def _expand_target_views(
    connection, store: str, selected: list[dict], view_limit: int,
) -> list[dict]:
    if not selected:
        return []
    by_product = {row["product_id"]: row for row in selected}
    placeholders = ",".join("?" for _ in by_product)
    query = (
        "SELECT i.store_id, i.product_id, i.position, i.source_url, p.title, "
        "p.category, p.category_group, p.catalog_rank FROM images i "
        "JOIN products p USING(store_id, product_id) WHERE i.store_id=? "
        f"AND i.product_id IN ({placeholders}) AND i.position<=? "
        "ORDER BY p.catalog_rank, p.product_id, i.position"
    )
    rows = connection.execute(
        query, [store, *by_product, view_limit],
    ).fetchall()
    return [{
        **dict(row),
        "selection_reasons": by_product[row["product_id"]]["selection_reasons"],
    } for row in rows]


def _store_dimension_distributions(
    connection, store: str, dimensions=SELECTION_DIMENSIONS,
) -> dict:
    total = connection.execute(
        "SELECT COUNT(*) FROM products WHERE store_id=?", (store,),
    ).fetchone()[0]
    result = {}
    for dimension in dimensions:
        rows = [dict(row) for row in connection.execute(
            "SELECT t.tag, COUNT(DISTINCT t.product_id) AS images "
            "FROM image_analysis_tags t WHERE t.store_id=? AND t.position=1 "
            "AND t.dimension=? GROUP BY t.tag ORDER BY images DESC, t.tag LIMIT 12",
            (store, dimension),
        )]
        analyzed = connection.execute(
            "SELECT COUNT(DISTINCT product_id) FROM image_analysis_tags "
            "WHERE store_id=? AND position=1 AND dimension=?", (store, dimension),
        ).fetchone()[0]
        for row in rows:
            row["share"] = round(row["images"] / analyzed, 4) if analyzed else 0
        result[dimension] = {
            "analyzed_products": analyzed,
            "population_products": total,
            "coverage": round(analyzed / total, 4) if total else 0,
            "values": rows,
        }
    return result


def _catalog_rows(connection, store: str, categories: list[str]) -> list[dict]:
    placeholders = ",".join("?" for _ in categories)
    query = (
        "SELECT i.store_id, i.product_id, i.position, i.source_url, p.title, "
        "p.category, p.category_group, p.catalog_rank FROM images i "
        "JOIN products p USING(store_id, product_id) WHERE i.position=1 "
        f"AND p.category_group IN ({placeholders}) AND i.store_id=? "
        "ORDER BY p.catalog_rank, p.product_id"
    )
    return [dict(row) for row in connection.execute(query, [*categories, store])]


def _analysis_index(connection, store: str, categories: list[str]) -> dict:
    category_slots = ",".join("?" for _ in categories)
    dimension_slots = ",".join("?" for _ in SELECTION_DIMENSIONS)
    query = (
        "SELECT t.product_id, t.dimension, t.tag, t.confidence "
        "FROM image_analysis_tags t JOIN products p USING(store_id, product_id) "
        "WHERE t.position=1 AND t.store_id=? "
        f"AND p.category_group IN ({category_slots}) "
        f"AND t.dimension IN ({dimension_slots})"
    )
    index = {}
    for row in connection.execute(query, [store, *categories, *SELECTION_DIMENSIONS]):
        dimensions = index.setdefault(row["product_id"], {})
        dimensions.setdefault(row["dimension"], []).append({
            "tag": row["tag"], "confidence": row["confidence"],
        })
    return index


def _validate_coverage(store: str, rows: list[dict], index: dict) -> None:
    missing = [
        f"{row['product_id']}:{dimension}"
        for row in rows for dimension in SELECTION_DIMENSIONS
        if not index.get(row["product_id"], {}).get(dimension)
    ]
    if missing:
        examples = ", ".join(missing[:3])
        raise ValueError(
            f"incomplete visual-dimension coverage for {store}: "
            f"{len(missing)} missing assignments ({examples})"
        )


def _dimension_distribution(rows: list[dict], index: dict, dimension: str) -> list[dict]:
    counts = {}
    for row in rows:
        for tag in index[row["product_id"]][dimension]:
            counts[tag["tag"]] = counts.get(tag["tag"], 0) + 1
    return [
        {"tag": tag, "images": count, "share": round(count / len(rows), 4)}
        for tag, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _representative(rows: list[dict], index: dict, dimension: str, tag: str) -> dict:
    candidates = []
    for row in rows:
        matches = [item for item in index[row["product_id"]][dimension] if item["tag"] == tag]
        if matches:
            candidates.append((max(item["confidence"] for item in matches), row))
    return min(
        candidates,
        key=lambda item: (-item[0], item[1].get("catalog_rank") or 10**9, item[1]["product_id"]),
    )[1]


def _add_reason(selected: dict, row: dict, reason: dict) -> None:
    target = selected.setdefault(row["product_id"], {**row, "selection_reasons": []})
    if reason not in target["selection_reasons"]:
        target["selection_reasons"].append(reason)


def _select_dimension_evidence(rows: list[dict], index: dict, selected: dict) -> dict:
    distributions = {}
    for dimension in SELECTION_DIMENSIONS:
        distribution = _dimension_distribution(rows, index, dimension)
        distributions[dimension] = distribution
        evidence_tags = [("typical", item) for item in distribution[:2]]
        minimum_boundary = max(1, round(len(rows) * 0.005))
        boundary_pool = [item for item in distribution if item["images"] >= minimum_boundary]
        boundary = min(boundary_pool, key=lambda item: (item["images"], item["tag"]))
        evidence_tags.append(("boundary", boundary))
        for evidence_role, item in evidence_tags:
            row = _representative(rows, index, dimension, item["tag"])
            _add_reason(selected, row, {
                "evidence_role": evidence_role, "dimension": dimension,
                "tag": item["tag"], "population_images": item["images"],
                "population_share": item["share"],
            })
    return distributions


def _select_cluster_evidence(rows: list[dict], index: dict, selected: dict) -> list[dict]:
    groups = {}
    for row in rows:
        signature, confidence = {}, []
        for dimension in SELECTION_DIMENSIONS:
            primary = min(
                index[row["product_id"]][dimension],
                key=lambda item: (-item["confidence"], item["tag"]),
            )
            signature[dimension] = primary["tag"]
            confidence.append(primary["confidence"])
        key = tuple(signature.items())
        group = groups.setdefault(key, {"signature": signature, "members": []})
        group["members"].append((sum(confidence) / len(confidence), row))
    ordered = sorted(groups.values(), key=lambda group: (
        -len(group["members"]), tuple(group["signature"].items()),
    ))
    minimum_boundary = max(1, round(len(rows) * 0.005))
    boundary_pool = [group for group in ordered if len(group["members"]) >= minimum_boundary]
    evidence_groups = [("typical", group) for group in ordered[:2]]
    if boundary_pool:
        evidence_groups.append(("boundary", min(
            boundary_pool, key=lambda group: (
                len(group["members"]), tuple(group["signature"].items()),
            ),
        )))
    for evidence_role, group in evidence_groups:
        row = min(group["members"], key=lambda item: (
            -item[0], item[1].get("catalog_rank") or 10**9, item[1]["product_id"],
        ))[1]
        _add_reason(selected, row, {
            "evidence_role": evidence_role, "selection_lens": "combined_visual_cluster",
            "signature": group["signature"], "population_images": len(group["members"]),
            "population_share": round(len(group["members"]) / len(rows), 4),
        })
    return [{
        "signature": group["signature"], "images": len(group["members"]),
        "share": round(len(group["members"]) / len(rows), 4),
    } for group in ordered]


def _select_store_evidence(connection, store: str, categories: list[str]) -> tuple[list[dict], dict]:
    rows = _catalog_rows(connection, store, categories)
    if not rows:
        raise ValueError(f"competitor evidence population is empty for {store}")
    index = _analysis_index(connection, store, categories)
    selected, category_plans = {}, {}
    for category in categories:
        category_rows = [row for row in rows if row["category_group"] == category]
        if not category_rows:
            category_plans[category] = {
                "population_images": 0, "analyzed_images": 0,
                "selected_images": 0, "status": "category_unavailable",
            }
            continue
        analyzed_rows = [row for row in category_rows if index.get(row["product_id"])]
        if not analyzed_rows:
            category_plans[category] = {
                "population_images": len(category_rows), "analyzed_images": 0,
                "selected_images": 0, "status": "dimension_tags_unavailable",
            }
            continue
        _validate_coverage(store, analyzed_rows, index)
        before = len(selected)
        dimensions = _select_dimension_evidence(analyzed_rows, index, selected)
        clusters = _select_cluster_evidence(analyzed_rows, index, selected)
        category_plans[category] = {
            "population_images": len(category_rows),
            "analyzed_images": len(analyzed_rows),
            "selected_images": len(selected) - before, "status": "available",
            "dimensions": dimensions, "visual_clusters": clusters,
        }
    chosen = sorted(selected.values(), key=lambda row: (
        row["category_group"], row.get("catalog_rank") or 10**9, row["product_id"],
    ))
    return chosen, {
        "population_images": len(rows), "analyzed_images": len(index),
        "selected_images": len(chosen), "categories": category_plans,
    }


def _public_image(item: dict) -> dict:
    download = item["download"].to_dict()
    download.pop("path", None)
    return {
        "image_id": item["image_id"], "role": item["role"],
        "store_id": item["store_id"], "product_id": item["product_id"],
        "position": item["position"], "category": item["category_group"],
        "title": item["title"],
        "selection_reasons": item["selection_reasons"], **download,
    }


def _compact_evidence(batch_results: list[dict], items: list[dict]) -> dict:
    return {
        "observations": [
            row for batch in batch_results for row in batch["observations"]
        ],
        "pattern_candidates": [
            row for batch in batch_results for row in batch["pattern_candidates"]
        ],
        "image_contexts": [{
            **{
                key: item.get(key) for key in (
                    "image_id", "store_id", "product_id", "position", "title",
                    "role", "selection_reasons",
                )
            },
            "category": item.get("category_group") or item.get("category"),
        } for item in items],
    }


def _validate_observation_batch(result: dict, batch: list[dict]) -> None:
    expected = sorted(item["image_id"] for item in batch)
    returned = sorted(row.get("image_id") for row in result.get("observations", []))
    if returned != expected:
        raise ValueError("saved report observation batch does not match its image scope")


def _analyze_image_batches(
    items: list[dict], analyzer, output: Path, progress,
    workers: int = REPORT_ANALYSIS_WORKERS,
) -> list[dict]:
    if workers < 1:
        raise ValueError("report analysis workers must be positive")
    chunks = [items[start:start + BATCH_SIZE] for start in range(0, len(items), BATCH_SIZE)]
    results = [None] * len(chunks)
    pending = {}
    completed_images = 0
    observations = output / "observations"
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for index, batch in enumerate(chunks):
            path = observations / f"batch-{index + 1:04d}.json"
            if path.is_file():
                result = json.loads(path.read_text(encoding="utf-8"))
                _validate_observation_batch(result, batch)
                results[index] = result
                completed_images += len(batch)
                continue
            pending[executor.submit(analyzer.analyze_images, batch)] = (index, batch, path)
        for future in as_completed(pending):
            index, batch, path = pending[future]
            result = future.result()
            _validate_observation_batch(result, batch)
            _write_json(path, result)
            results[index] = result
            completed_images += len(batch)
            progress(
                "analyzing_all_images",
                35 + round(completed_images / len(items) * 45),
            )
    return results


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


def _validate_competitor_brand_claims(report: dict, items: list[dict]) -> None:
    section = next(
        (row for row in report["sections"] if row["section_id"] == "competitive_gap"),
        None,
    )
    if section is None:
        raise ValueError("report is missing competitive_gap section")
    image_stores = {item["image_id"]: item["store_id"] for item in items}
    for store_id, brand in COMPETITOR_BRANDS.items():
        valid = False
        for claim in section["claims"]:
            claim_text = f"{claim.get('conclusion', '')} {claim.get('derivation', '')}".lower()
            if brand.lower() not in claim_text and store_id.lower() not in claim_text:
                continue
            evidence = claim.get("evidence") or {}
            evidence_ids = (
                evidence.get("support_image_ids", [])
                + evidence.get("example_image_ids", [])
            )
            if any(image_stores.get(image_id) == store_id for image_id in evidence_ids):
                valid = True
                break
        if not valid:
            raise ValueError(
                f"competitive_gap requires a named {brand} claim with matching brand evidence"
            )


def run_report_analysis(args, progress=lambda _stage, _value: None) -> Path:
    if not args.endpoint or not args.api_key:
        raise ValueError("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY are required")
    rows, competitor_evidence = _select_rows(
        args.db, args.target_store, args.categories,
        key_category_limit=args.key_category_limit,
        sample_per_category=args.sample_per_category,
        sample_seed=args.sample_seed,
    )
    output = Path(args.output)
    image_cache = _shared_image_cache(args, output)
    progress("downloading_hd_images", 5)
    items, failures = [], []
    for index, row in enumerate(rows, 1):
        try:
            download = download_high_resolution_image(
                store_id=row["store_id"], product_id=row["product_id"],
                position=row["position"], source_url=row["source_url"],
                output_dir=output / "images", timeout=args.download_timeout,
                cache_dir=image_cache,
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
    key_category_analysis = competitor_evidence["target"]
    primary_categories = [
        row["category"] for row in key_category_analysis["key_categories"]
    ]
    categories = competitor_evidence["categories"]
    downloaded_by_category = {
        category: sum(
            item["role"] == "target" and item["category_group"] == category
            for item in items
        )
        for category in categories
    }
    key_category_analysis["key_categories"] = [
        {**row, "downloaded_images": downloaded_by_category[row["category"]]}
        for row in key_category_analysis["key_categories"]
    ]
    key_category_analysis["supplementary_categories"] = [
        {**row, "downloaded_images": downloaded_by_category[row["category"]]}
        for row in key_category_analysis["supplementary_categories"]
    ]
    scope = {
        "target_store": args.target_store, "categories": categories,
        "primary_categories": primary_categories,
        "supplementary_categories": [
            row["category"] for row in key_category_analysis["supplementary_categories"]
        ],
        "target_products": len({
            item["product_id"] for item in items if item["role"] == "target"
        }),
        "target_images": target_total,
        "competitor_images": sum(item["role"] == "competitor" for item in items),
        "competitor_population_images": sum(
            store["analyzed_images"] for store in competitor_evidence["stores"].values()
        ),
        "competitor_catalog_population_images": sum(
            store["population_images"] for store in competitor_evidence["stores"].values()
        ),
        "competitor_sampling": "仅从已有完整12维标签覆盖的可比品类分布中选择典型图与有效边界图",
        "competitor_brands": COMPETITOR_BRANDS,
        "competitor_selection_dimensions": list(SELECTION_DIMENSIONS),
        "analysis_dimensions": {
            "target_catalog_tag_dimensions": list(DIMENSIONS),
            "competitor_catalog_tag_dimensions": list(SELECTION_DIMENSIONS),
            "gpt_visible_observation_fields": list(OBSERVABLE_FIELDS),
        },
        "store_profile": key_category_analysis["store_profile"],
        "key_category_analysis": key_category_analysis,
        "positions": [1, 2], "excluded_metrics": ["曝光", "点击", "转化", "销量", "ROI"],
        "excluded_analysis": ["人群画像", "代表红人", "敏感模特属性推断"],
        "whitepaper_coverage": {
            "included": [
                "店铺基本信息", "重点品类", "风格划分", "产品卖点", "动作",
                "常见搭配", "拍摄布景", "拍摄风格", "模特画像", "对标竞品",
            ],
            "excluded": ["人群画像", "代表红人"],
        },
    }
    manifest = {
        "status": "analyzing", "scope": scope, "model": args.deployment,
        "image_detail": "high", "selected_images": len(rows),
        "downloaded_images": len(items), "download_failures": failures,
        "cache_hits": sum(item["download"].cache_hit for item in items),
        "network_downloads": sum(not item["download"].cache_hit for item in items),
        "competitor_evidence": competitor_evidence,
        "images": [_public_image(item) for item in items],
    }
    _write_json(output / "manifest.json", manifest)
    usage = AnalysisUsageRecorder(
        output / "usage.jsonl", output / "usage-summary.json",
        total_images=len(items), deployment=args.deployment,
        pricing=pricing_for_deployment(args.deployment),
    )
    analyzer = AzureOpenAIReportAnalyzer(
        AzureOpenAIOptions(
            args.endpoint, args.api_key, args.deployment,
            getattr(args, "auth_type", "api_key"),
        ),
        usage.record,
    )
    batches = []
    try:
        batches = _analyze_image_batches(items, analyzer, output, progress)
        evidence = {
            **_compact_evidence(batches, items),
            "competitor_evidence": competitor_evidence,
        }
        _write_json(output / "image-observations.json", evidence)
        progress("synthesizing_report_sections", 85)
        report = analyzer.synthesize(evidence, scope, output / "section-checkpoints")
        _validate_claim_references(report, {item["image_id"] for item in items})
        _validate_competitor_brand_claims(report, items)
    except Exception:
        usage.finish("failed", completed_images=sum(len(batch["observations"]) for batch in batches))
        raise
    usage.finish("complete", completed_images=len(items))
    result = {
        **manifest, "status": "complete", "executive_summary": report["executive_summary"],
        "sections": report["sections"], "image_observations": evidence["observations"],
        "analysis_contract": {
            "section_ids": list(SECTION_IDS),
            "target_catalog_tag_dimensions": list(DIMENSIONS),
            "competitor_catalog_tag_dimensions": list(SELECTION_DIMENSIONS),
            "gpt_visible_observation_fields": list(OBSERVABLE_FIELDS),
            "excluded_analysis": scope["excluded_analysis"],
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
        pricing=pricing_for_deployment(args.deployment),
    )
    analyzer = AzureOpenAIReportAnalyzer(
        AzureOpenAIOptions(
            args.endpoint, args.api_key, args.deployment,
            getattr(args, "auth_type", "api_key"),
        ),
        usage.record,
    )
    progress("revising_section", 40)
    try:
        revised = analyzer.revise(section, args.suggestion, evidence, result["scope"])
        _validate_claim_references(
            {"sections": [revised]}, {row["image_id"] for row in result["images"]},
        )
        if args.section_id == "competitive_gap":
            _validate_competitor_brand_claims(
                {"sections": [revised]}, result["images"],
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
        "categories": None, "key_category_limit": 3,
        "sample_per_category": 20, "sample_seed": "report-analysis",
        "download_timeout": 30, "image_cache": None,
        "deployment": "gpt-5.6-sol",
        "endpoint": os.environ.get("AZURE_OPENAI_ENDPOINT"),
        "api_key": os.environ.get("AZURE_OPENAI_KEY"),
        "auth_type": "api_key",
    }
    values.update(overrides)
    return SimpleNamespace(**values)
