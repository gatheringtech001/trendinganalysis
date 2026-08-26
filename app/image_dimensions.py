from __future__ import annotations

import json


MAX_STORE_SAMPLES = 12


def _selected_stores(store_id: str, options: dict, stores: dict) -> list[str]:
    if "stores" not in options:
        if store_id and store_id not in stores:
            raise ValueError("unknown image analysis store")
        return [store_id] if store_id else list(stores)
    selected = [
        value.strip() for value in str(options["stores"]).split(",")
        if value.strip()
    ]
    if not selected or len(selected) != len(set(selected)):
        raise ValueError("image analysis stores must be unique")
    if any(value not in stores for value in selected):
        raise ValueError("unknown image analysis store")
    return selected


def _analysis_rows(store) -> list[tuple[dict, dict]]:
    with store.lock:
        if store.image_dimension_rows_cache is None:
            rows = store._all(
                "SELECT i.store_id, i.product_id, i.position, i.source_url image_url, "
                "i.url_sha256, p.title, p.category, p.market, p.channel, p.price_usd, "
                "ia.analysis_version, ia.analysis_status, ia.analysis_method, "
                "ia.tags_json analysis_tags_json, ia.confidence_json analysis_confidence_json "
                "FROM image_analysis ia JOIN images i USING(store_id, product_id, position) "
                "JOIN products p USING(store_id, product_id) "
                "ORDER BY i.store_id, p.catalog_rank, i.position"
            )
            store.image_dimension_rows_cache = [
                (row, json.loads(row["analysis_tags_json"])) for row in rows
            ]
    return store.image_dimension_rows_cache


def _tag_vocabulary(rows: list[tuple[dict, dict]],
                    allowed: tuple[str, ...]) -> dict[str, set[str]]:
    vocabulary = {dimension: set() for dimension in allowed}
    for _, tags in rows:
        for dimension in allowed:
            vocabulary[dimension].update(
                str(tag) for tag in tags.get(dimension, []) if str(tag)
            )
    return vocabulary


def _selected_filters(options: dict, allowed: tuple[str, ...],
                      vocabulary: dict[str, set[str]]) -> dict[str, str]:
    raw = options.get("filters")
    if raw in (None, ""):
        parsed = {}
    elif isinstance(raw, dict):
        parsed = raw
    elif isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ValueError("image analysis filters must be valid JSON") from error
    else:
        raise ValueError("image analysis filters must be an object")
    if not isinstance(parsed, dict):
        raise ValueError("image analysis filters must be an object")
    if any(dimension not in allowed for dimension in parsed):
        raise ValueError("unknown image analysis dimension")
    selected = {}
    for dimension in allowed:
        if dimension not in parsed:
            continue
        tag = str(parsed[dimension]).strip()
        if not tag or tag not in vocabulary[dimension]:
            raise ValueError("unknown image analysis tag")
        selected[dimension] = tag
    return selected


def _dimension_options(rows: list[tuple[dict, dict]],
                       allowed: tuple[str, ...],
                       vocabulary: dict[str, set[str]]) -> list[dict]:
    counts = {dimension: {} for dimension in allowed}
    for _, tags in rows:
        for dimension in allowed:
            for tag in {str(value) for value in tags.get(dimension, []) if str(value)}:
                counts[dimension][tag] = counts[dimension].get(tag, 0) + 1
    return [
        {
            "dimension": dimension,
            "tags": [
                {"tag": tag, "images": counts[dimension].get(tag, 0)}
                for tag in sorted(
                    vocabulary[dimension],
                    key=lambda value: (-counts[dimension].get(value, 0), value),
                )
            ],
        }
        for dimension in allowed
    ]


def _store_counts(rows: list[tuple[dict, dict]], stores: dict) -> dict[str, int]:
    counts = {store_id: 0 for store_id in stores}
    for row, _ in rows:
        counts[row["store_id"]] += 1
    return counts


def _store_options(counts: dict[str, int], stores: dict) -> list[dict]:
    return [
        {
            "store_id": store_id,
            "name": name,
            "analyzed_images": counts[store_id],
        }
        for store_id, name in stores.items()
    ]


def _matches(tags: dict, selected_filters: dict[str, str]) -> bool:
    return all(
        selected_tag in {str(tag) for tag in tags.get(dimension, [])}
        for dimension, selected_tag in selected_filters.items()
    )


def _store_groups(store, rows: list[tuple[dict, dict]], selected_stores: list[str],
                  stores: dict, analyzed_counts: dict[str, int],
                  images_per_store: int) -> list[dict]:
    groups = []
    for store_id in selected_stores:
        store_rows = [row for row, _ in rows if row["store_id"] == store_id]
        images = len(store_rows)
        groups.append({
            "store_id": store_id,
            "store_name": stores[store_id],
            "images": images,
            "share": round(images / analyzed_counts[store_id], 4)
            if analyzed_counts[store_id] else 0,
            "items": store._decode_image_analysis([
                dict(row) for row in store_rows[:images_per_store]
            ]),
        })
    return groups


def build_image_dimensions(store, store_id: str, options: dict,
                           allowed: tuple[str, ...], stores: dict) -> dict:
    all_rows = _analysis_rows(store)
    vocabulary = _tag_vocabulary(all_rows, allowed)
    selected_stores = _selected_stores(store_id, options, stores)
    selected_filters = _selected_filters(options, allowed, vocabulary)
    images_per_store = min(
        MAX_STORE_SAMPLES, max(1, int(options.get("images_per_store", 6)))
    )
    all_counts = _store_counts(all_rows, stores)
    selected_set = set(selected_stores)
    selected_rows = [row for row in all_rows if row[0]["store_id"] in selected_set]
    analyzed_counts = _store_counts(selected_rows, stores)
    matched_rows = [
        row for row in selected_rows if selected_filters and _matches(row[1], selected_filters)
    ]
    return {
        "dimension_options": _dimension_options(selected_rows, allowed, vocabulary),
        "selected_filters": selected_filters,
        "stores": _store_options(all_counts, stores),
        "selected_stores": selected_stores,
        "analyzed_images": sum(analyzed_counts.values()),
        "matched_images": len(matched_rows),
        "store_groups": _store_groups(
            store, matched_rows, selected_stores, stores,
            analyzed_counts, images_per_store,
        ),
        "images_per_store": images_per_store,
    }
