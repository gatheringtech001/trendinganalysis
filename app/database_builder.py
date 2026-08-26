from __future__ import annotations

import json
import os
import sqlite3
from collections import Counter
from pathlib import Path


STORES = {
    "princess_polly": "Princess Polly",
    "motel": "Motel Rocks",
    "prettylittlething": "PrettyLittleThing",
    "aloruh_shein": "Aloruh(shein)",
    "aloruh_local": "Aloruh(local)",
}
SNAPSHOT = "2026-08-18"

ALORUH_DATA_STEMS = {
    "aloruh_shein": ("aloruh_shein",),
    "aloruh_local": ("aloruh", "aloruh_customer"),
}

IMAGE_ANALYSIS_DIMENSIONS = (
    "product_category", "silhouette_fit", "design_elements", "occasion",
    "composition", "view_action", "selling_points", "scene",
    "material_texture", "color_pattern", "visual_language", "styling",
    "lighting", "model_state", "graphic_overlay",
)
LEGACY_IMAGE_ANALYSIS_DIMENSIONS = IMAGE_ANALYSIS_DIMENSIONS[:-3]


def category_group(value: str) -> str:
    text = (value or "Unclassified").upper()
    rules = (
        ("DRESS", "DRESSES"), ("TOP", "TOPS"), ("SKIRT", "SKIRTS"),
        ("TROUSER", "TROUSERS"), ("PANT", "TROUSERS"),
        ("SWIM", "SWIMWEAR"), ("BIKINI", "SWIMWEAR"),
        ("SHORT", "SHORTS"), ("JEAN", "JEANS"),
        ("JACKET", "OUTERWEAR"), ("COAT", "OUTERWEAR"),
        ("SHOE", "SHOES"), ("BAG", "ACCESSORIES"),
        ("JEWEL", "ACCESSORIES"), ("EARRING", "ACCESSORIES"),
        ("NECKLACE", "ACCESSORIES"),
    )
    return next((group for token, group in rules if token in text), text[:60])


def _jsonl(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def _jsonl_fragments(data_dir: Path, stem: str):
    paths = [data_dir / f"{stem}.jsonl", *sorted(data_dir.glob(f"{stem}_*.jsonl"))]
    for path in paths:
        yield from _jsonl(path)


def _store_jsonl(data_dir: Path, kind: str, store_id: str):
    stems = ALORUH_DATA_STEMS.get(store_id)
    if stems:
        for stem in stems:
            path = data_dir / f"{kind}_{stem}.jsonl"
            if path.exists():
                yield from _jsonl(path)
        return
    yield from _jsonl_fragments(data_dir, f"{kind}_{store_id}")


def _source_store_id(store_id: str) -> str | None:
    if store_id == "aloruh_shein":
        return None
    if store_id == "aloruh_local":
        return "aloruh"
    return store_id


def _visual_store_id(store_id: str) -> str:
    return "aloruh_local" if store_id == "aloruh" else store_id


def _json_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, list) else []


def _product_row(store_id: str, row: dict) -> tuple:
    source_type = row.get("source_type", "")
    channel = row.get("channel") or (
        "customer_dataset" if source_type == "customer_dataset" else "official_site"
    )
    return (
        store_id, str(row.get("product_id", "")), row.get("handle", ""),
        row.get("title", ""), row.get("category") or "Unclassified",
        category_group(row.get("category", "")), row.get("market") or "US", channel,
        row.get("price_usd"),
        row.get("was_price_usd"), float(row.get("discount_rate") or 0),
        int(bool(row.get("available"))), int(bool(row.get("on_sale"))),
        json.dumps(row.get("sizes", []), ensure_ascii=False),
        json.dumps(row.get("colours", []), ensure_ascii=False),
        row.get("primary_image_url", ""), int(row.get("image_count") or 0),
        row.get("source_url", ""), source_type,
        row.get("category_method", ""), row.get("category_confidence"),
        row.get("catalog_rank"),
        row.get("product_detail_views"), row.get("available_quantity"),
        int(bool(row.get("top_seller"))),
        row.get("estimated_sold_label"), int(bool(row.get("sales_is_estimated"))),
        row.get("bestseller_rank"), row.get("retrieved_at", ""),
    )


def _review_row(store_id: str, row: dict) -> tuple:
    product_id = str(row["product_id"]) if row.get("product_id") else None
    return (
        store_id, str(row.get("review_id", "")), product_id,
        row.get("product_title"), "product" if product_id else "brand",
        row.get("source_type", ""), row.get("created_at", ""),
        row.get("rating"), row.get("title", ""), row.get("content", ""),
        row.get("sentiment_score"),
        int(bool(row.get("verified_buyer"))) if row.get("verified_buyer") is not None else None,
        json.dumps(row.get("themes", []), ensure_ascii=False),
        row.get("source_url", ""),
    )


def _visual_row(row: dict) -> tuple:
    return (
        _visual_store_id(row.get("store_id", "")), str(row.get("product_id", "")),
        row.get("source_url", ""), row.get("content_sha256", ""),
        int(row.get("width") or 0), int(row.get("height") or 0),
        float(row.get("brightness") or 0), float(row.get("saturation") or 0),
        float(row.get("warmth") or 0), float(row.get("edge_density") or 0),
        float(row.get("border_brightness") or 0),
        float(row.get("border_saturation") or 0),
        row.get("dominant_family", "未知"), int(bool(row.get("valid"))),
        row.get("exclusion_reason", ""),
    )


def _image_analysis_rows(store_id: str, row: dict) -> tuple[tuple, list[tuple]] | None:
    analysis = row.get("analysis")
    if not isinstance(analysis, dict):
        return None
    tags, confidence = analysis.get("tags"), analysis.get("confidence")
    dimensions = (LEGACY_IMAGE_ANALYSIS_DIMENSIONS
                  if analysis.get("analysis_version") == "fashion-image-v1"
                  else IMAGE_ANALYSIS_DIMENSIONS)
    expected = set(dimensions)
    if not isinstance(tags, dict) or set(tags) != expected:
        raise ValueError("image analysis tags do not match the declared analysis version")
    if not isinstance(confidence, dict) or set(confidence) != expected:
        raise ValueError("image analysis confidence does not match the declared analysis version")
    key = (store_id, str(row.get("product_id", "")), int(row.get("position") or 0))
    record = key + (
        analysis.get("analysis_version", ""), analysis.get("analysis_status", ""),
        analysis.get("analysis_method", ""),
        json.dumps(tags, ensure_ascii=False),
        json.dumps(confidence, ensure_ascii=False),
    )
    tag_rows = [
        key + (dimension, str(tag), float(confidence[dimension]))
        for dimension in dimensions
        for tag in tags[dimension]
    ]
    return record, tag_rows


def _unique_image_rows(rows) -> list[dict]:
    result = []
    seen_urls: set[str] = set()
    for row in rows:
        url = str(row.get("source_url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        result.append(row)
    return result


def build_database(db_path: Path, data_dir: Path) -> None:
    db_path, data_dir = Path(db_path), Path(data_dir)
    temp_path = db_path.with_suffix(db_path.suffix + ".building")
    if temp_path.exists():
        temp_path.unlink()
    connection = sqlite3.connect(temp_path)
    connection.executescript(
        """
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        CREATE TABLE products (
            store_id TEXT NOT NULL, product_id TEXT NOT NULL, handle TEXT,
            title TEXT NOT NULL, category TEXT NOT NULL, category_group TEXT NOT NULL,
            market TEXT NOT NULL, channel TEXT NOT NULL,
            price_usd REAL, was_price_usd REAL, discount_rate REAL NOT NULL,
            available INTEGER NOT NULL, on_sale INTEGER NOT NULL,
            sizes_json TEXT NOT NULL, colours_json TEXT NOT NULL,
            primary_image_url TEXT, image_count INTEGER NOT NULL,
            source_url TEXT, source_type TEXT NOT NULL, category_method TEXT,
            category_confidence REAL, catalog_rank INTEGER, product_detail_views INTEGER,
            available_quantity INTEGER, top_seller INTEGER NOT NULL,
            estimated_sold_label TEXT, sales_is_estimated INTEGER NOT NULL,
            bestseller_rank INTEGER,
            retrieved_at TEXT, PRIMARY KEY (store_id, product_id)
        );
        CREATE TABLE images (
            store_id TEXT NOT NULL, product_id TEXT NOT NULL, position INTEGER NOT NULL,
            source_url TEXT NOT NULL, url_sha256 TEXT, sample_product INTEGER NOT NULL,
            PRIMARY KEY (store_id, product_id, position),
            UNIQUE (store_id, source_url)
        );
        CREATE TABLE reviews (
            store_id TEXT NOT NULL, review_id TEXT NOT NULL, product_id TEXT,
            product_title TEXT, review_scope TEXT NOT NULL, source_type TEXT,
            created_at TEXT, rating REAL, title TEXT, content TEXT,
            sentiment_score REAL, verified_buyer INTEGER, themes_json TEXT NOT NULL,
            source_url TEXT, PRIMARY KEY (store_id, review_id)
        );
        CREATE TABLE visual_features (
            store_id TEXT NOT NULL, product_id TEXT NOT NULL, source_url TEXT,
            content_sha256 TEXT, width INTEGER NOT NULL, height INTEGER NOT NULL,
            brightness REAL NOT NULL, saturation REAL NOT NULL, warmth REAL NOT NULL,
            edge_density REAL NOT NULL, border_brightness REAL NOT NULL,
            border_saturation REAL NOT NULL, dominant_family TEXT NOT NULL,
            valid INTEGER NOT NULL, exclusion_reason TEXT,
            PRIMARY KEY (store_id, product_id)
        );
        CREATE TABLE image_analysis (
            store_id TEXT NOT NULL, product_id TEXT NOT NULL, position INTEGER NOT NULL,
            analysis_version TEXT NOT NULL, analysis_status TEXT NOT NULL,
            analysis_method TEXT NOT NULL, tags_json TEXT NOT NULL,
            confidence_json TEXT NOT NULL,
            PRIMARY KEY (store_id, product_id, position)
        );
        CREATE TABLE image_analysis_tags (
            store_id TEXT NOT NULL, product_id TEXT NOT NULL, position INTEGER NOT NULL,
            dimension TEXT NOT NULL, tag TEXT NOT NULL, confidence REAL NOT NULL,
            PRIMARY KEY (store_id, product_id, position, dimension, tag)
        );
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """
    )
    for store_id in STORES:
        rows = (
            _product_row(store_id, row)
            for row in _store_jsonl(data_dir, "catalog", store_id)
        )
        connection.executemany("INSERT INTO products VALUES(" + ",".join("?" * 29) + ")", rows)
        image_rows = _unique_image_rows(
            _store_jsonl(data_dir, "images", store_id)
        )
        images = (
            (store_id, str(row.get("product_id", "")), int(row.get("position") or 0),
             row.get("source_url", ""), row.get("url_sha256", ""),
             int(bool(row.get("sample_product"))))
            for row in image_rows
        )
        connection.executemany("INSERT INTO images VALUES(?,?,?,?,?,?)", images)
        for image in image_rows:
            analysis_rows = _image_analysis_rows(store_id, image)
            if not analysis_rows:
                continue
            record, tags = analysis_rows
            connection.execute("INSERT INTO image_analysis VALUES(?,?,?,?,?,?,?,?)", record)
            connection.executemany(
                "INSERT INTO image_analysis_tags VALUES(?,?,?,?,?,?)", tags,
            )
        connection.execute(
            "UPDATE products SET "
            "image_count = (SELECT COUNT(*) FROM images i "
            "WHERE i.store_id = products.store_id "
            "AND i.product_id = products.product_id), "
            "primary_image_url = COALESCE((SELECT source_url FROM images i "
            "WHERE i.store_id = products.store_id "
            "AND i.product_id = products.product_id "
            "ORDER BY position LIMIT 1), '') "
            "WHERE store_id = ?",
            [store_id],
        )
        source_store_id = _source_store_id(store_id)
        review_rows = _json_rows(data_dir / f"reviews_{source_store_id}.json") if source_store_id else []
        connection.executemany(
            "INSERT INTO reviews VALUES(" + ",".join("?" * 14) + ")",
            (_review_row(store_id, row) for row in review_rows),
        )
        for kind in ("reviews", "ugc"):
            count = len(_json_rows(data_dir / f"{kind}_{source_store_id}.json")) if source_store_id else 0
            connection.execute("INSERT INTO metadata VALUES(?,?)", (f"{kind}:{store_id}", str(count)))
    visual_rows = _json_rows(data_dir / "visual_features.json")
    connection.executemany(
        "INSERT INTO visual_features VALUES(" + ",".join("?" * 15) + ")",
        (_visual_row(row) for row in visual_rows if _visual_store_id(row.get("store_id", "")) in STORES),
    )
    _add_download_counts(connection, data_dir)
    connection.executescript(
        """
        CREATE INDEX products_store_category ON products(store_id, category_group);
        CREATE INDEX products_category ON products(category_group);
        CREATE INDEX products_title ON products(title COLLATE NOCASE);
        CREATE INDEX products_views ON products(product_detail_views DESC);
        CREATE INDEX images_product ON images(store_id, product_id, position);
        CREATE INDEX images_store ON images(store_id);
        CREATE INDEX reviews_product ON reviews(store_id, product_id);
        CREATE INDEX reviews_scope ON reviews(store_id, review_scope);
        CREATE INDEX visual_features_store ON visual_features(store_id, valid);
        CREATE INDEX image_analysis_store ON image_analysis(store_id);
        CREATE INDEX image_analysis_tags_dimension
            ON image_analysis_tags(dimension, tag, store_id);
        PRAGMA optimize;
        """
    )
    connection.commit()
    connection.close()
    os.replace(temp_path, db_path)


def _add_download_counts(connection: sqlite3.Connection, data_dir: Path) -> None:
    rows = _json_rows(data_dir / "downloaded_images.json")
    counts = Counter(
        str(row.get("path", "")).replace("/", "\\").split("\\")[1]
        for row in rows if len(str(row.get("path", "")).replace("/", "\\").split("\\")) > 1
    )
    for store_id in STORES:
        source_ids = ALORUH_DATA_STEMS.get(store_id, (store_id,))
        connection.execute(
            "INSERT INTO metadata VALUES(?,?)",
            (f"downloaded:{store_id}", str(sum(counts[source_id] for source_id in source_ids))),
        )
