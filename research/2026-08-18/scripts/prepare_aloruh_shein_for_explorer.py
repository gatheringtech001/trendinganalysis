from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data"
DEFAULT_OUTPUT = ROOT.parent / "2026-08-14" / "data"

CATEGORY_NAMES = {
    "12480": "Maxi Dresses", "12475": "Mini Dresses", "1779": "Tank Tops",
    "1733": "Blouses", "1738": "T-Shirts", "12476": "Midi Dresses",
    "2223": "Crop Tops", "1732": "Skirts", "1780": "Two-Piece Sets",
    "1727": "Mini Dresses", "1866": "Bikini Sets", "1734": "Knit Tops",
    "1912": "Shorts", "1882": "Bodysuits", "12478": "Dresses",
    "1740": "Trousers", "2977": "Suits", "2218": "Knit Dresses",
    "2270": "Lingerie Sets", "1739": "Blazers", "1932": "Denim Tops",
    "1860": "Jumpsuits", "1735": "Jackets", "8821": "Lingerie",
    "2176": "Beach Cover-Ups", "2217": "Knit Tops", "1776": "Jackets",
    "2203": "Bras", "2220": "Knit Sets", "1931": "Denim Dresses",
    "3091": "Formal Dresses", "3050": "Trench Coats", "1862": "Sleepwear",
    "14497": "Lingerie Sets", "1773": "Hoodies", "2193": "One-Piece Swimwear",
    "3051": "Coats", "2209": "Sleepwear", "9548": "Formal Dresses",
    "8820": "Lingerie", "3054": "Faux Fur Coats", "1934": "Jeans",
    "12318": "Cardigans", "14418": "Lingerie Bodysuits", "1880": "Sleepwear",
    "8836": "One-Piece Swimwear", "8822": "Lingerie Sets", "1748": "Shoes",
    "8035": "Maxi Skirts", "4296": "Underwear", "1890": "Plus Size Tops",
    "1937": "Denim Skirts", "2052": "Denim Sets", "2185": "Sports Tops",
    "2188": "Sports Shorts", "2222": "Knit Trousers", "2221": "Skirts",
    "2219": "Cardigans", "2211": "Nightgowns",
}


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _valid_images(values: list[str]) -> list[str]:
    blocked = ("bg-grey-solid-color", "images3_ccc/2024/07/25")
    result: list[str] = []
    positions: dict[str, int] = {}
    for value in values:
        url = _clean_url(str(value))
        if not url or any(token in url for token in blocked):
            continue
        key = _image_asset_key(url)
        position = positions.get(key)
        if position is None:
            positions[key] = len(result)
            result.append(url)
        elif _image_score(url) > _image_score(result[position]):
            result[position] = url
    return result


def _dedupe_product_images(products: list[dict]) -> tuple[list[dict], int]:
    seen_assets: set[str] = set()
    result: list[dict] = []
    original_count = sum(len(row.get("image_urls") or []) for row in products)
    for source in products:
        row = dict(source)
        images = []
        for url in row.get("image_urls") or []:
            asset = _image_asset_key(url)
            if asset in seen_assets:
                continue
            seen_assets.add(asset)
            images.append(url)
        row["image_urls"] = images
        row["image_count"] = len(images)
        row["primary_image_url"] = images[0] if images else ""
        result.append(row)
    return result, original_count - len(seen_assets)


def _image_asset_key(url: str) -> str:
    parts = urlsplit(url)
    directory, _, filename = parts.path.rpartition("/")
    stem = filename.rsplit(".", 1)[0]
    core = re.sub(r"_thumbnail_[^/]+$", "", stem, flags=re.I)
    return f"{parts.netloc.lower()}{directory}/{core}"


def _image_score(url: str) -> tuple[int, int]:
    match = re.search(r"_thumbnail_(\d+)x(?:\d+)?", url, re.I)
    resolution = int(match.group(1)) if match else 10_000
    extension = urlsplit(url).path.rsplit(".", 1)[-1].lower()
    format_score = {"webp": 3, "avif": 2, "jpg": 1, "jpeg": 1}.get(extension, 0)
    return resolution, format_score


def _raw_cards(payload: dict) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for page in payload.get("catalog_pages") or []:
        for card in page.get("cards") or []:
            product_id = str(card.get("goods_id") or "")
            if product_id and product_id not in result:
                result[product_id] = card
    return result


def _raw_card_count(payload: dict) -> int:
    return sum(len(page.get("cards") or []) for page in payload.get("catalog_pages") or [])


def _sample_cards(input_dir: Path) -> dict[str, dict]:
    path = input_dir / "aloruh_shein_sample_selection.partial.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(row.get("goods_id") or row.get("product_id")): row
        for rows in (payload.get("layers") or {}).values()
        for row in rows if row.get("goods_id") or row.get("product_id")
    }


def _clean_url(value: str) -> str:
    parts = urlsplit(urljoin("https://sg.shein.com", value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _supplement_rows(cards: dict[str, dict], existing: set[str], retrieved_at: str) -> list[dict]:
    rows = []
    for product_id, card in cards.items():
        if product_id in existing:
            continue
        text = str(card.get("text") or "")
        sold = re.search(r"\b(\d+(?:\.\d+)?\+?)\s+sold\b", text, re.I)
        bestseller = re.search(r"#(\d+)\s+Bestseller\b", text, re.I)
        raw_images = card.get("image_urls") or []
        images = raw_images.split() if isinstance(raw_images, str) else list(raw_images)
        rows.append({
            "product_id": product_id, "title": card.get("title", ""),
            "category_id": str(card.get("category_id") or ""),
            "price_sgd": float(card["price_sgd"]) if card.get("price_sgd") else None,
            "price_usd": float(card["price_usd"]) if card.get("price_usd") else None,
            "discount_rate": float(card.get("discount") or 0) / 100,
            "estimated_sold_label": f"{sold.group(1)} sold" if sold else None,
            "sales_is_estimated": bool(sold and re.search("Estimated", text, re.I)),
            "bestseller_rank": int(bestseller.group(1)) if bestseller else None,
            "catalog_rank": len(existing) + len(rows) + 1, "image_urls": images,
            "source_type": "official_shein_sorted_brand_page",
            "source_url": _clean_url(str(card.get("source_url") or card.get("href") or "")),
            "retrieved_at": retrieved_at,
        })
    return rows


def _dedupe_catalog(rows: list[dict]) -> list[dict]:
    result: dict[str, dict] = {}
    for row in rows:
        product_id = str(row.get("product_id") or "")
        if product_id and product_id not in result:
            result[product_id] = row
    return list(result.values())


def _merge_refresh(catalog: list[dict], refresh_rows: list[dict]) -> tuple[list[dict], int, int]:
    result = {str(row["product_id"]): row for row in _dedupe_catalog(catalog)}
    updated = 0
    added = 0
    for refresh in refresh_rows:
        product_id = str(refresh["product_id"])
        existing = result.get(product_id)
        if existing is None:
            result[product_id] = refresh
            added += 1
            continue
        merged = dict(existing)
        for key in (
            "title", "category_id", "price_sgd", "price_usd", "catalog_rank",
            "source_type", "source_url", "retrieved_at",
        ):
            if refresh.get(key) not in (None, ""):
                merged[key] = refresh[key]
        merged["discount_rate"] = refresh.get("discount_rate", merged.get("discount_rate", 0))
        if refresh.get("estimated_sold_label"):
            merged["estimated_sold_label"] = refresh["estimated_sold_label"]
            merged["sales_is_estimated"] = bool(refresh.get("sales_is_estimated"))
        if refresh.get("bestseller_rank") is not None:
            merged["bestseller_rank"] = refresh["bestseller_rank"]
        if _valid_images(list(refresh.get("image_urls") or [])):
            merged["image_urls"] = list(refresh["image_urls"])
        result[product_id] = merged
        updated += 1
    return list(result.values()), updated, added


def _display_price(row: dict, card: dict) -> tuple[float | None, float | None, float]:
    text = str(card.get("text") or "")
    discount_match = re.search(r"-(\d{1,2})%", text)
    price_match = re.search(r"S\$\s*(\d+(?:\.\d+)?)", text)
    base_sgd, base_usd = row.get("price_sgd"), row.get("price_usd")
    current_usd = base_usd
    if price_match and base_sgd and base_usd:
        current_usd = round(float(price_match.group(1)) * float(base_usd) / float(base_sgd), 2)
    discount = (
        int(discount_match.group(1)) / 100
        if discount_match else float(row.get("discount_rate") or 0)
    )
    was_price = base_usd if current_usd and base_usd and current_usd < base_usd else None
    return current_usd, was_price, discount


def _product(row: dict, detail: dict | None, card: dict) -> dict:
    price, was_price, discount = _display_price(row, card)
    detail_images = _valid_images(list(detail.get("image_urls") or [])) if detail else []
    images = detail_images or _valid_images(list(row.get("image_urls") or []))
    colours = [detail["color"]] if detail and detail.get("color") else []
    category_id = str(row.get("category_id") or "")
    return {
        "store_id": "aloruh", "market": "SG", "channel": "shein_sg",
        "product_id": str(row["product_id"]), "handle": f"shein-{row['product_id']}",
        "title": row.get("title", ""), "brand": "Aloruh",
        "category": CATEGORY_NAMES.get(category_id, f"SHEIN category {category_id}"),
        "category_method": "official_shein_category_id", "category_confidence": 1.0,
        "price_usd": price, "was_price_usd": was_price,
        "discount_rate": discount, "on_sale": bool(discount),
        "available": bool(detail.get("available")) if detail else True,
        "sizes": list(detail.get("sizes") or []) if detail else [], "colours": colours,
        "primary_image_url": images[0] if images else "", "image_count": len(images),
        "image_urls": images, "catalog_rank": row.get("catalog_rank"),
        "estimated_sold_label": row.get("estimated_sold_label"),
        "sales_is_estimated": bool(row.get("sales_is_estimated")),
        "bestseller_rank": row.get("bestseller_rank"),
        "top_seller": False,
        "source_type": detail.get("source_type") if detail else row.get("source_type", ""),
        "source_url": row.get("source_url", ""), "retrieved_at": row.get("retrieved_at", ""),
    }


def prepare(input_dir: Path, output_dir: Path) -> dict:
    catalog = _dedupe_catalog(_jsonl(input_dir / "catalog_aloruh_shein.jsonl"))
    details = {str(row["product_id"]): row for row in _jsonl(input_dir / "details_aloruh_shein.jsonl")}
    payload = json.loads((input_dir / "aloruh_shein_browser_export.json").read_text(encoding="utf-8"))
    cards = _raw_cards(payload)
    sample_cards = _sample_cards(input_dir)
    cards.update(sample_cards)
    existing = {str(row["product_id"]) for row in catalog}
    retrieved_at = str(payload.get("retrieved_at") or "")
    catalog.extend(_supplement_rows(sample_cards, existing, retrieved_at))
    refresh_path = input_dir / "aloruh_shein_browser_export.recollect.partial.json"
    refresh_payload = json.loads(refresh_path.read_text(encoding="utf-8")) if refresh_path.exists() else {}
    refresh_cards = _raw_cards(refresh_payload)
    refresh_retrieved_at = str(refresh_payload.get("retrieved_at") or retrieved_at)
    refresh_rows = _supplement_rows(refresh_cards, set(), refresh_retrieved_at)
    base_products = len(catalog)
    catalog, refresh_updated, refresh_added = _merge_refresh(catalog, refresh_rows)
    cards.update(refresh_cards)
    products = [
        _product(row, details.get(str(row["product_id"])), cards.get(str(row["product_id"]), {}))
        for row in catalog
    ]
    products, image_duplicates_removed = _dedupe_product_images(products)
    image_rows = [
        {
            "store_id": "aloruh", "market": "SG", "channel": "shein_sg",
            "product_id": row["product_id"], "position": position,
            "source_url": url, "url_sha256": hashlib.sha256(url.encode()).hexdigest(),
            "content_sha256": None, "retrieved_at": row["retrieved_at"],
            "sample_product": row["product_id"] in details,
        }
        for row in products for position, url in enumerate(row["image_urls"], 1)
    ]
    if len({row["product_id"] for row in products}) != len(products):
        raise ValueError("Aloruh SHEIN product_id is not unique")
    if set(details) - {row["product_id"] for row in products}:
        raise ValueError("Aloruh SHEIN detail contains an orphan product_id")
    _write_jsonl(output_dir / "catalog_aloruh_shein.jsonl", products)
    _write_jsonl(output_dir / "images_aloruh_shein.jsonl", image_rows)
    summary = {
        "products": len(products), "deep_detail_products": len(details),
        "images": len(image_rows), "market": "SG", "channel": "shein_sg",
        "image_duplicate_rows_removed": image_duplicates_removed,
        "products_with_images": sum(bool(row["image_urls"]) for row in products),
        "base_products": base_products,
        "refresh_raw_cards": _raw_card_count(refresh_payload),
        "refresh_unique_products": len(refresh_cards),
        "refresh_duplicate_cards": _raw_card_count(refresh_payload) - len(refresh_cards),
        "refresh_updated_products": refresh_updated,
        "refresh_added_products": refresh_added,
        "refresh_complete": bool((refresh_payload.get("collection_state") or {}).get("complete")),
        "refresh_last_complete_page": int((refresh_payload.get("collection_state") or {}).get("last_complete_page") or 0),
        "refresh_failures": list(refresh_payload.get("failures") or []),
    }
    (output_dir / "aloruh_shein_import_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Aloruh SHEIN SG data for Fashion Scope")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(prepare(args.input_dir, args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
