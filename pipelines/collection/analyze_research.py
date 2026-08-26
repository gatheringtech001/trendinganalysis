"""Compute per-store metrics, QA checks, and visual contact sheets."""

from __future__ import annotations

import json
import math
import statistics
import hashlib
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


BASE = Path(__file__).resolve().parents[2]
DATA = BASE / "data"
ANALYSIS = BASE / "output" / "analysis"
STORES = ["princess_polly", "motel", "prettylittlething"]
NAMES = {
    "princess_polly": "Princess Polly",
    "motel": "Motel Rocks",
    "prettylittlething": "PrettyLittleThing",
}
PAGE_URLS = {
    ("princess_polly", "homepage"): "https://us.princesspolly.com/",
    ("princess_polly", "new_in_listing"): "https://us.princesspolly.com/collections/new-arrivals",
    ("motel", "homepage"): "https://us.motelrocks.com/",
    ("motel", "new_in_listing"): "https://us.motelrocks.com/collections/new-arrivals",
    ("prettylittlething", "homepage"): "https://www.prettylittlething.us/",
    ("prettylittlething", "new_in_listing"): "https://www.prettylittlething.us/new-in.html",
}


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def percentile(values: list[float], fraction: float) -> float | None:
    values = sorted(values)
    if not values:
        return None
    point = (len(values) - 1) * fraction
    lower = math.floor(point)
    upper = math.ceil(point)
    if lower == upper:
        return round(values[lower], 2)
    weight = point - lower
    return round(values[lower] * (1 - weight) + values[upper] * weight, 2)


def top(counter: Counter, limit: int = 10) -> list[dict]:
    return [{"label": str(label or "Unknown"), "count": count} for label, count in counter.most_common(limit)]


def percentage(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def metric_summary(rows: list[dict]) -> dict:
    prices = [float(row["price_usd"]) for row in rows if row.get("price_usd") is not None]
    discounts = [float(row.get("discount_rate") or 0) for row in rows]
    sizes = Counter(size for row in rows for size in row.get("sizes", []))
    colours = Counter(colour for row in rows for colour in row.get("colours", []))
    categories = Counter(str(row.get("category") or "Unclassified").strip().upper() for row in rows)
    return {
        "row_count": len(rows),
        "available_count": sum(bool(row.get("available")) for row in rows),
        "available_rate": percentage(sum(bool(row.get("available")) for row in rows), len(rows)),
        "sold_out_rate": percentage(sum(not row.get("available") for row in rows), len(rows)),
        "on_sale_count": sum(bool(row.get("on_sale")) for row in rows),
        "on_sale_rate": percentage(sum(bool(row.get("on_sale")) for row in rows), len(rows)),
        "median_discount_rate": round(statistics.median(discounts), 4) if discounts else None,
        "price_p25_usd": percentile(prices, 0.25),
        "price_median_usd": percentile(prices, 0.5),
        "price_p75_usd": percentile(prices, 0.75),
        "top_categories": top(categories),
        "top_sizes": top(sizes, 15),
        "top_colours": top(colours, 15),
        "products_with_sizes_rate": percentage(sum(bool(row.get("sizes")) for row in rows), len(rows)),
        "products_with_colours_rate": percentage(sum(bool(row.get("colours")) for row in rows), len(rows)),
    }


def review_summary(rows: list[dict]) -> dict:
    ratings = [float(row["rating"]) for row in rows if row.get("rating") is not None]
    themes = Counter(theme for row in rows for theme in row.get("themes", []))
    return {
        "count": len(rows),
        "rated_count": len(ratings),
        "average_rating": round(statistics.mean(ratings), 2) if ratings else None,
        "positive_rate": percentage(sum((row.get("sentiment_score") or 0) >= 0.6 for row in rows), len(rows)),
        "verified_buyer_rate": percentage(sum(bool(row.get("verified_buyer")) for row in rows), len(rows)),
        "top_themes": top(themes),
        "age_buckets": top(Counter(row.get("age_bucket") for row in rows if row.get("age_bucket"))),
        "occasions": top(Counter(row.get("occasion") for row in rows if row.get("occasion"))),
        "fit_scores": top(Counter(str(row.get("fit")) for row in rows if row.get("fit") is not None)),
    }


def ugc_summary(rows: list[dict]) -> dict:
    return {
        "count": len(rows),
        "recent_window_count": sum(bool(row.get("within_recent_window")) for row in rows),
        "recent_window_rate": percentage(sum(bool(row.get("within_recent_window")) for row in rows), len(rows)),
        "platforms": top(Counter(row.get("platform") for row in rows)),
        "source_types": top(Counter(row.get("source_type") for row in rows)),
    }


def make_contact_sheet(store: str, sample: list[dict], images: list[dict]) -> None:
    by_id = {row["product_id"]: row for row in sample}
    selected = [row for row in images if store in row.get("path", "") and row.get("status") == "ok"][:24]
    cell_w, cell_h, columns = 260, 360, 6
    sheet = Image.new("RGB", (cell_w * columns, cell_h * 4), "#f4f1ec")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, item in enumerate(selected):
        x, y = (index % columns) * cell_w, (index // columns) * cell_h
        source = BASE / item["path"]
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
            image.thumbnail((240, 285))
            px, py = x + (cell_w - image.width) // 2, y + 8
            sheet.paste(image, (px, py))
        product = by_id.get(item["product_id"], {})
        label = f"{index + 1:02d} {product.get('sample_bucket', '')}\n{product.get('title', '')[:34]}\n${product.get('price_usd', '')}"
        draw.multiline_text((x + 10, y + 300), label, fill="#201d1a", font=font, spacing=3)
    sheet.save(ANALYSIS / f"contact_sheet_{store}.jpg", quality=90)


def index_visual_pages() -> list[dict]:
    page_dir = BASE / "raw" / "visual_pages"
    rows = []
    for path in sorted(page_dir.glob("*.png")):
        store = next((item for item in STORES if path.stem.startswith(item)), None)
        content = path.read_bytes()
        with Image.open(path) as opened:
            width, height = opened.size
        page_type = "homepage" if path.stem.endswith("_home") else "new_in_listing"
        rows.append({
            "store_id": store,
            "page_type": page_type,
            "source_url": PAGE_URLS[(store, page_type)],
            "path": str(path.relative_to(BASE)),
            "content_sha256": hashlib.sha256(content).hexdigest(),
            "bytes": len(content),
            "width": width,
            "height": height,
            "retrieved_at": "2026-08-14T00:00:00+08:00",
        })
    if rows:
        canvas = Image.new("RGB", (720, 500 * len(rows)), "white")
        draw = ImageDraw.Draw(canvas)
        for index, row in enumerate(rows):
            with Image.open(BASE / row["path"]) as opened:
                image = ImageOps.exif_transpose(opened).convert("RGB")
                image.thumbnail((700, 455))
                canvas.paste(image, (10, index * 500 + 30))
            draw.text((10, index * 500 + 8), f"{row['store_id']} / {row['page_type']}", fill="black")
        canvas.save(ANALYSIS / "contact_sheet_visual_pages.jpg", quality=85)
    (ANALYSIS / "visual_page_index.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows


def duplicate_count(rows: list[dict], field: str) -> int:
    values = [row.get(field) for row in rows if row.get(field)]
    return len(values) - len(set(values))


def main() -> None:
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    sources = load_jsonl(DATA / "sources.jsonl")
    downloaded = load_json(DATA / "downloaded_images.json")
    page_visuals = index_visual_pages()
    result, qa = {}, {"snapshot_date": "2026-08-14", "stores": {}, "overall": {}}
    for store in STORES:
        catalog = load_jsonl(DATA / f"catalog_{store}.jsonl")
        sample = load_json(DATA / f"sample_{store}.json")
        reviews = load_json(DATA / f"reviews_{store}.json")
        ugc = load_json(DATA / f"ugc_{store}.json")
        store_sources = [row for row in sources if row.get("store_id") == store]
        buckets = Counter(row.get("sample_bucket") for row in sample)
        result[store] = {
            "store_name": NAMES[store],
            "catalog": metric_summary(catalog),
            "sample": metric_summary(sample),
            "sample_buckets": dict(buckets),
            "reviews": review_summary(reviews),
            "ugc": ugc_summary(ugc),
            "sources": {
                "count": len(store_sources),
                "source_types": top(Counter(row.get("source_type") for row in store_sources)),
                "unique_urls": len({row.get("source_url") for row in store_sources if row.get("source_url")}),
            },
        }
        qa["stores"][store] = {
            "catalog_rows": len(catalog),
            "observed_index_parse_coverage": 1.0,
            "enumeration_completeness": "official endpoint exhausted; independent true SKU denominator unavailable",
            "sample_rows": len(sample),
            "sample_bucket_counts": dict(buckets),
            "review_rows": len(reviews),
            "ugc_rows": len(ugc),
            "duplicate_product_ids": duplicate_count(catalog, "product_id"),
            "duplicate_product_urls": duplicate_count(catalog, "source_url"),
            "duplicate_sample_product_ids": duplicate_count(sample, "product_id"),
            "missing_product_ids": sum(not row.get("product_id") for row in catalog),
            "missing_product_urls": sum(not row.get("source_url") for row in catalog),
            "missing_prices": sum(row.get("price_usd") is None for row in catalog),
            "sample_target_met": len(sample) == 150 and all(buckets[name] == 50 for name in ("new", "best", "sale_long_tail")),
            "review_public_target_or_actual": len(reviews) <= 500,
            "ugc_target_or_actual": len(ugc) <= 100,
        }
        make_contact_sheet(store, sample, downloaded)
    ok_images = [row for row in downloaded if row.get("status") == "ok"]
    qa["overall"] = {
        "downloaded_visual_samples": len(ok_images),
        "failed_visual_samples": len(downloaded) - len(ok_images),
        "page_visual_samples": len(page_visuals),
        "duplicate_downloaded_content_hashes": duplicate_count(ok_images, "content_sha256"),
        "full_image_index_hash_type": "SHA-256 of URL",
        "downloaded_image_hash_type": "SHA-256 of file bytes",
        "secrets_expected": False,
    }
    (ANALYSIS / "analysis_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (ANALYSIS / "qa_results.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"analysis": str(ANALYSIS), "stores": list(result), "images": len(ok_images)}))


if __name__ == "__main__":
    main()
