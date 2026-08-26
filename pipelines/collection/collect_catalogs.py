from __future__ import annotations

import argparse
import concurrent.futures
import gzip
import hashlib
import html
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW = PROJECT_ROOT / "data" / "raw"
DATA = PROJECT_ROOT / "data"
IMAGES = PROJECT_ROOT / "data" / "sample_images"
RETRIEVED_AT = "2026-08-14T00:00:00+08:00"
UA = "Mozilla/5.0 (compatible; store-research/1.0; +read-only)"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA})

SHOPIFY_STORES = {
    "princess_polly": {"name": "Princess Polly", "base": "https://us.princesspolly.com"},
    "motel": {"name": "Motel Rocks", "base": "https://us.motelrocks.com"},
}
ALORUH_API = "https://aloruh.com/wp-json/wc/store/v1/products"
STORE_IDS = (*SHOPIFY_STORES, "prettylittlething", "aloruh")
SIZE_OPTION = re.compile(
    r"(?:SHOE\s+)?US\s+\d{1,2}|\d{1,2}|(?:XXS|XS|S|M|L|XL|XXL|XXXL|OS|ONE\s+SIZE)"
    r"|(?:XXS|XS|S|M|L|XL|XXL)/(?:XXS|XS|S|M|L|XL|XXL)|W\d{2}\s+L\d{2}",
    re.I,
)


def sha(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def save_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def save_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def request_json(url: str, **kwargs) -> dict:
    for attempt in range(3):
        try:
            response = SESSION.get(url, timeout=60, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("unreachable")


def request_text(url: str) -> str:
    response = SESSION.get(url, timeout=60)
    response.raise_for_status()
    return response.text


def shopify_products(base: str, path: str = "/products.json", cap: int | None = None) -> list[dict]:
    products: list[dict] = []
    for page in range(1, 100):
        batch = request_json(base + path, params={"limit": 250, "page": page}).get("products", [])
        products.extend(batch)
        if len(batch) < 250 or (cap and len(products) >= cap):
            break
    return products[:cap] if cap else products


def normalize_shopify(store_id: str, base: str, product: dict, rank: int) -> dict:
    variants = product.get("variants", [])
    prices = [float(v["price"]) for v in variants if v.get("price") not in (None, "")]
    compares = [float(v["compare_at_price"]) for v in variants if v.get("compare_at_price") not in (None, "")]
    option_values = [v for option in product.get("options", []) for v in option.get("values", [])]
    sizes = [v for v in option_values if SIZE_OPTION.fullmatch(str(v).strip())]
    colours = [v for v in option_values if v not in sizes and str(v).lower() != "default title"]
    if store_id == "motel" and not colours:
        title_colour = re.search(r"\bin\s+(.+)$", product.get("title", ""), re.I)
        colours = [title_colour.group(1).strip()] if title_colour else []
    current = min(prices) if prices else None
    was = max(compares) if compares else None
    discount = round((was - current) / was, 4) if current is not None and was and was > current else 0
    url = f"{base}/products/{product['handle']}"
    tags = product.get("tags", [])
    record = {
        "store_id": store_id,
        "market": "US",
        "product_id": str(product.get("id", "")),
        "handle": product.get("handle", ""),
        "title": product.get("title", ""),
        "brand": product.get("vendor", ""),
        "category": product.get("product_type", "") or "Unclassified",
        "price_usd": current,
        "was_price_usd": was,
        "discount_rate": discount,
        "on_sale": discount > 0,
        "available": any(v.get("available") for v in variants),
        "available_variant_count": sum(bool(v.get("available")) for v in variants),
        "variant_count": len(variants),
        "sizes": sizes,
        "colours": colours,
        "tags": tags,
        "created_at": product.get("created_at"),
        "updated_at": product.get("updated_at"),
        "catalog_rank": rank,
        "image_count": len(product.get("images", [])),
        "primary_image_url": (product.get("images") or [{}])[0].get("src", ""),
        "image_urls": [item.get("src", "") for item in product.get("images", [])],
        "source_type": "official_catalog_api",
        "source_url": url,
        "retrieved_at": RETRIEVED_AT,
    }
    record["content_hash"] = sha(json.dumps(record, sort_keys=True, ensure_ascii=False))
    return record


def _minor_amount(value: str | int | None, minor_unit: int) -> float | None:
    if value in (None, ""):
        return None
    return int(value) / (10 ** minor_unit)


def _aloruh_category(title: str, categories: list[dict]) -> tuple[str, str]:
    if categories:
        return categories[0].get("name") or "Unclassified", "official"
    text = title.lower()
    for token, category in (
        ("dress", "Dresses"),
        ("blouse", "Tops"),
        ("corset", "Tops"),
        ("cardigan", "Outerwear"),
        ("skirt", "Skirts"),
        ("set", "Sets"),
    ):
        if token in text:
            return category, "title_inference"
    return "Unclassified", "unavailable"


def normalize_woocommerce(store_id: str, product: dict, rank: int) -> dict:
    title = html.unescape(re.sub(r"<[^>]+>", "", product.get("name", "")))
    prices = product.get("prices") or {}
    minor_unit = int(prices.get("currency_minor_unit") or 2)
    current = _minor_amount(prices.get("price"), minor_unit)
    regular = _minor_amount(prices.get("regular_price"), minor_unit)
    was = regular if regular is not None and current is not None and regular > current else None
    discount = round((was - current) / was, 4) if was else 0
    attributes = product.get("attributes") or []

    def terms_for(*names: str) -> list[str]:
        expected = {name.lower() for name in names}
        return [
            term.get("name", "")
            for attribute in attributes
            if str(attribute.get("name", "")).lower() in expected
            for term in attribute.get("terms", [])
            if term.get("name")
        ]

    category, category_source = _aloruh_category(title, product.get("categories") or [])
    images = [item.get("src", "") for item in product.get("images", []) if item.get("src")]
    variations = product.get("variations") or []
    sizes = terms_for("size")
    colours = terms_for("colour", "color")
    record = {
        "store_id": store_id,
        "market": "US",
        "product_id": str(product.get("id", "")),
        "handle": product.get("slug", ""),
        "title": title,
        "brand": "Aloruh",
        "category": category,
        "category_source": category_source,
        "price_usd": current,
        "was_price_usd": was,
        "discount_rate": discount,
        "on_sale": bool(product.get("on_sale")),
        "available": bool(product.get("is_in_stock")),
        "available_variant_count": len(variations) if product.get("is_in_stock") else 0,
        "variant_count": len(variations),
        "sizes": sizes,
        "colours": colours,
        "tags": [item.get("name", "") for item in product.get("tags", []) if item.get("name")],
        "created_at": None,
        "updated_at": None,
        "catalog_rank": rank,
        "image_count": len(images),
        "primary_image_url": images[0] if images else "",
        "image_urls": images,
        "official_review_count": int(product.get("review_count") or 0),
        "source_type": "official_woocommerce_store_api",
        "source_url": product.get("permalink", ""),
        "retrieved_at": RETRIEVED_AT,
    }
    record["content_hash"] = sha(json.dumps(record, sort_keys=True, ensure_ascii=False))
    return record


def collect_woocommerce() -> tuple[list[dict], dict[str, list[str]]]:
    raw = request_json(ALORUH_API, params={"per_page": 100, "orderby": "date", "order": "desc"})
    (RAW / "aloruh_robots.txt").write_text(request_text("https://aloruh.com/robots.txt"), encoding="utf-8")
    (RAW / "aloruh_wp_sitemap.xml").write_text(request_text("https://aloruh.com/wp-sitemap.xml"), encoding="utf-8")
    with gzip.open(RAW / "aloruh_woocommerce_products.json.gz", "wt", encoding="utf-8") as stream:
        json.dump(raw, stream, ensure_ascii=False)
    rows = [normalize_woocommerce("aloruh", product, index + 1) for index, product in enumerate(raw)]
    return rows, {
        "new": [row["product_id"] for row in rows],
        "best": [],
        "sale": [row["product_id"] for row in rows if row["on_sale"]],
    }


def collect_shopify(store_id: str, config: dict) -> tuple[list[dict], dict[str, list[str]]]:
    raw = shopify_products(config["base"])
    RAW.mkdir(parents=True, exist_ok=True)
    with gzip.open(RAW / f"{store_id}_products.json.gz", "wt", encoding="utf-8") as stream:
        json.dump(raw, stream, ensure_ascii=False)
    rows = [normalize_shopify(store_id, config["base"], product, index + 1) for index, product in enumerate(raw)]
    ranks: dict[str, list[str]] = {"new": [], "best": [], "sale": []}
    if store_id == "princess_polly":
        handles = {"new": ["new"], "best": ["best-selling-dresses", "best-selling-tops", "best-selling-bottoms", "best-selling-swim", "best-selling-outerwear", "best-selling-shoes-accessories"], "sale": ["sale"]}
    else:
        handles = {"new": ["new-in"], "best": [], "sale": ["sale"]}
    for bucket, collection_handles in handles.items():
        for handle in collection_handles:
            items = shopify_products(config["base"], f"/collections/{handle}/products.json", 250)
            ranks[bucket].extend(str(item.get("id")) for item in items)
    if store_id == "motel":
        ranked = [row for row in rows if re.search(r"best|most wanted|trending|viral", " ".join(map(str, row["tags"])), re.I)]
        ranks["best"] = [row["product_id"] for row in ranked]
    return rows, ranks


def algolia_post(path: str, body: dict) -> dict:
    key = os.environ.get("PLT_ALGOLIA_API_KEY")
    if not key:
        raise RuntimeError("PLT_ALGOLIA_API_KEY is required")
    headers = {"x-algolia-api-key": key, "x-algolia-application-id": "PBL6WQH9VL", "Content-Type": "application/json"}
    response = SESSION.post("https://pbl6wqh9vl-dsn.algolia.net" + path, headers=headers, json=body, timeout=90)
    response.raise_for_status()
    return response.json()


def algolia_rank(facet: str) -> list[str]:
    params = urlencode({
        "facetFilters": json.dumps(["brand:PrettyLittleThing", facet]),
        "getRankingInfo": "true",
        "hitsPerPage": 250,
        "page": 0,
    })
    payload = algolia_post("/1/indexes/*/queries", {
        "requests": [{"indexName": "prettylittlethingus-dbz-prod", "params": params}]
    })
    return [hit.get("objectID", "") for hit in payload["results"][0].get("hits", [])]


def collect_plt() -> tuple[list[dict], dict[str, list[str]]]:
    body: dict = {"filters": 'brand:"PrettyLittleThing"', "hitsPerPage": 1000}
    raw: list[dict] = []
    while True:
        payload = algolia_post("/1/indexes/prettylittlethingus-dbz-prod/browse", body)
        raw.extend(payload.get("hits", []))
        cursor = payload.get("cursor")
        if not cursor:
            break
        body = {"cursor": cursor}
    with gzip.open(RAW / "prettylittlething_algolia.json.gz", "wt", encoding="utf-8") as stream:
        json.dump(raw, stream, ensure_ascii=False)
    rows: list[dict] = []
    for index, hit in enumerate(raw, 1):
        url = f"https://www.prettylittlething.us/product/{hit.get('slug', '')}?colour={hit.get('colour', '')}"
        record = {
            "store_id": "prettylittlething", "market": "US", "product_id": hit.get("objectID", ""),
            "handle": hit.get("slug", ""), "title": hit.get("name", ""), "brand": hit.get("brand", ""),
            "category": hit.get("categoryTaxonomy") or hit.get("department") or "Unclassified",
            "price_usd": hit.get("price"), "was_price_usd": hit.get("wasPrice"),
            "discount_rate": round(float(hit.get("discountPercentage") or 0) / 100, 4),
            "on_sale": bool(hit.get("discountPercentage")), "available": bool(hit.get("isOnStock")),
            "available_variant_count": hit.get("validVariantCount", 0), "variant_count": len(hit.get("variantSkus", [])),
            "sizes": hit.get("sizes", []), "colours": hit.get("colourFacets", []),
            "tags": hit.get("categorySlugs", []), "created_at": hit.get("createdAt"), "updated_at": hit.get("lastUpdate"),
            "catalog_rank": index, "image_count": len(hit.get("images", [])),
            "primary_image_url": (hit.get("images") or [""])[0], "image_urls": hit.get("images", []),
            "product_detail_views": hit.get("productDetailViews"), "available_quantity": hit.get("availableQuantity"),
            "top_seller": str(hit.get("isTopSellerRevenue", "false")).lower() == "true",
            "source_type": "official_search_index", "source_url": url, "retrieved_at": RETRIEVED_AT,
        }
        record["content_hash"] = sha(json.dumps(record, sort_keys=True, ensure_ascii=False))
        rows.append(record)
    ranks = {"new": algolia_rank("categorySlugs:womens-new-in"),
             "best": algolia_rank("categorySlugs:wk48-best-sellers"),
             "sale": algolia_rank("categorySlugs:womens-sale")}
    return rows, ranks


def stratified_sale(rows: list[dict], used: set[str], count: int) -> list[dict]:
    candidates = [r for r in rows if r["product_id"] not in used and r["on_sale"]]
    candidates.sort(key=lambda r: (r["category"], r["price_usd"] or 0, r["product_id"]))
    categories = sorted({r["category"] for r in candidates})
    selected: list[dict] = []
    while len(selected) < count and candidates:
        for category in categories:
            match = next((r for r in candidates if r["category"] == category), None)
            if match:
                selected.append(match)
                candidates.remove(match)
                if len(selected) == count:
                    break
    return selected


def build_sample(rows: list[dict], ranks: dict[str, list[str]]) -> list[dict]:
    by_id = {row["product_id"]: row for row in rows}
    selected: list[dict] = []
    used: set[str] = set()
    for bucket in ("new", "best"):
        bucket_rows = [by_id[item] for item in ranks[bucket] if item in by_id and item not in used][:50]
        for rank, row in enumerate(bucket_rows, 1):
            copy = dict(row); copy["sample_bucket"] = bucket; copy["bucket_rank"] = rank
            selected.append(copy); used.add(row["product_id"])
        if len(bucket_rows) < 50:
            fill = [r for r in rows if r["product_id"] not in used][:50 - len(bucket_rows)]
            for row in fill:
                copy = dict(row); copy["sample_bucket"] = bucket + "_fallback"; copy["bucket_rank"] = None
                selected.append(copy); used.add(row["product_id"])
    for row in stratified_sale(rows, used, 50):
        copy = dict(row); copy["sample_bucket"] = "sale_long_tail"; copy["bucket_rank"] = None
        selected.append(copy); used.add(row["product_id"])
    if len(selected) < 150:
        for row in rows:
            if row["product_id"] in used:
                continue
            copy = dict(row); copy["sample_bucket"] = "sale_long_tail_fallback"; copy["bucket_rank"] = None
            selected.append(copy); used.add(row["product_id"])
            if len(selected) == 150:
                break
    return selected


def image_index(store_id: str, rows: list[dict], sample: list[dict]) -> list[dict]:
    sample_ids = {row["product_id"] for row in sample}
    indexed: list[dict] = []
    for row in rows:
        for position, url in enumerate(row.get("image_urls", []), 1):
            indexed.append({"store_id": store_id, "product_id": row["product_id"], "position": position,
                            "sample_product": row["product_id"] in sample_ids, "source_url": url,
                            "url_sha256": sha(url), "content_sha256": None, "retrieved_at": RETRIEVED_AT})
    return indexed


def download_image(item: dict) -> dict:
    url = item["primary_image_url"]
    if not url:
        return {"store_id": item["store_id"], "product_id": item["product_id"], "status": "missing_url"}
    try:
        response = SESSION.get(url, timeout=45)
        response.raise_for_status()
        ext = ".jpg" if "png" not in response.headers.get("Content-Type", "").lower() else ".png"
        target = IMAGES / item["store_id"] / f"{item['product_id'].replace('/', '_').replace('#', '_')}{ext}"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.content)
        return {"store_id": item["store_id"], "product_id": item["product_id"], "status": "ok", "path": str(target.relative_to(PROJECT_ROOT)),
                "content_sha256": sha(response.content), "bytes": len(response.content), "source_url": url}
    except Exception as exc:
        return {"store_id": item["store_id"], "product_id": item["product_id"], "status": "error", "error": str(exc)[:180], "source_url": url}


def _load_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def main(selected_store: str = "all") -> None:
    RAW.mkdir(parents=True, exist_ok=True); DATA.mkdir(parents=True, exist_ok=True)
    selected = set(STORE_IDS) if selected_store == "all" else {selected_store}
    all_rows: dict[str, list[dict]] = {}
    rankings: dict[str, dict[str, list[str]]] = {}
    for store_id, config in SHOPIFY_STORES.items():
        if store_id in selected:
            all_rows[store_id], rankings[store_id] = collect_shopify(store_id, config)
    if "prettylittlething" in selected:
        all_rows["prettylittlething"], rankings["prettylittlething"] = collect_plt()
    if "aloruh" in selected:
        all_rows["aloruh"], rankings["aloruh"] = collect_woocommerce()
    downloads: list[dict] = []
    samples: dict[str, list[dict]] = {}
    for store_id, rows in all_rows.items():
        sample = build_sample(rows, rankings[store_id])
        samples[store_id] = sample
        save_jsonl(DATA / f"catalog_{store_id}.jsonl", rows)
        save_json(DATA / f"sample_{store_id}.json", sample)
        save_jsonl(DATA / f"images_{store_id}.jsonl", image_index(store_id, rows, sample))
        visual_subset = [sample[i] for i in range(0, len(sample), max(1, len(sample) // 24))][:24]
        downloads.extend(visual_subset)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(download_image, downloads))
    previous_downloads = _load_json(DATA / "downloaded_images.json", [])
    merged_downloads = [row for row in previous_downloads if row.get("store_id") not in selected]
    merged_downloads.extend(results)
    save_json(DATA / "downloaded_images.json", merged_downloads)
    summary = _load_json(DATA / "catalog_summary.json", {})
    summary.update({store: {"catalog_rows": len(rows), "available_rows": sum(bool(r["available"]) for r in rows),
                       "sample_rows": len(samples[store]), "image_rows": sum(len(r.get("image_urls", [])) for r in rows)}
               for store, rows in all_rows.items()})
    save_json(DATA / "catalog_summary.json", summary)
    print(json.dumps({store: summary[store] for store in all_rows}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description="Collect official store catalogs")
        parser.add_argument("--store", choices=("all", *STORE_IDS), default="all")
        main(parser.parse_args().store)
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise
