from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import urljoin, urlsplit, urlunsplit


BASE_URL = "https://sg.shein.com"


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _float(value: object) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _clean_url(value: str) -> str:
    absolute = urljoin(BASE_URL, value)
    parts = urlsplit(absolute)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _image_urls(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        url = urljoin(BASE_URL, value)
        if url and url not in result:
            result.append(url)
    return result


def is_challenge_url(url: str) -> bool:
    return "/risk/challenge" in url or "captcha_type=909" in url


def normalize_card(card: dict, page_number: int, page_rank: int, retrieved_at: str) -> dict:
    product_id = str(card.get("goods_id") or "")
    if not product_id:
        raise ValueError("SHEIN product card is missing goods_id")
    text = str(card.get("text") or "")
    sold = re.search(r"\b(\d+(?:\.\d+)?\+?)\s+sold\b", text, re.I)
    bestseller = re.search(r"#(\d+)\s+Bestseller\b", text, re.I)
    images = _image_urls(list(card.get("image_urls") or []))
    discount = _float(card.get("discount"))
    row = {
        "store_id": "aloruh",
        "channel": "shein_sg",
        "market": "SG",
        "product_id": product_id,
        "store_code": str(card.get("store_code") or ""),
        "spu": str(card.get("spu") or ""),
        "sku": str(card.get("sku") or ""),
        "title": str(card.get("title") or "").strip(),
        "category_id": str(card.get("category_id") or ""),
        "price_sgd": _float(card.get("price_sgd")),
        "price_usd": _float(card.get("price_usd")),
        "discount_rate": round(discount / 100, 4) if discount is not None else None,
        "estimated_sold_label": f"{sold.group(1)} sold" if sold else None,
        "sales_is_estimated": bool(sold and re.search(r"Estimated", text, re.I)),
        "bestseller_rank": int(bestseller.group(1)) if bestseller else None,
        "catalog_page": page_number,
        "catalog_rank": (page_number - 1) * 120 + page_rank,
        "image_count": len(images),
        "primary_image_url": images[0] if images else "",
        "image_urls": images,
        "source_type": "official_shein_brand_page",
        "source_url": _clean_url(str(card.get("href") or "")),
        "retrieved_at": retrieved_at,
    }
    row["content_hash"] = sha(json.dumps(row, ensure_ascii=False, sort_keys=True))
    return row


def parse_product_group(group: dict, source_url: str, retrieved_at: str) -> tuple[dict, list[dict]]:
    match = re.search(r"-p-(\d+)[.]html", source_url)
    if not match:
        raise ValueError(f"Cannot identify SHEIN product id from {source_url}")
    product_id = match.group(1)
    variants = list(group.get("hasVariant") or [])
    offers = [item.get("offers") or {} for item in variants]
    prices = [price for price in (_float(item.get("price")) for item in offers) if price is not None]
    sizes = list(dict.fromkeys(str(item.get("size")) for item in variants if item.get("size")))
    urls = _image_urls(list(group.get("image") or []))
    detail = {
        "store_id": "aloruh",
        "channel": "shein_sg",
        "market": "SG",
        "product_id": product_id,
        "product_group_id": str(group.get("productGroupID") or ""),
        "title": str(group.get("name") or ""),
        "color": str(group.get("color") or ""),
        "sizes": sizes,
        "variant_count": len(variants),
        "available": any(str(item.get("availability") or "").endswith("InStock") for item in offers),
        "price_min_sgd": min(prices) if prices else None,
        "price_max_sgd": max(prices) if prices else None,
        "image_count": len(urls),
        "image_urls": urls,
        "source_type": "official_shein_product_page_jsonld",
        "source_url": _clean_url(source_url),
        "retrieved_at": retrieved_at,
    }
    detail["content_hash"] = sha(json.dumps(detail, ensure_ascii=False, sort_keys=True))
    images = [
        {
            "store_id": "aloruh",
            "channel": "shein_sg",
            "market": "SG",
            "product_id": product_id,
            "color": detail["color"],
            "position": position,
            "source_url": url,
            "url_sha256": sha(url),
            "content_sha256": None,
            "retrieved_at": retrieved_at,
        }
        for position, url in enumerate(urls, 1)
    ]
    return detail, images


def normalize_browser_export(payload: dict) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    retrieved_at = str(payload.get("retrieved_at") or "")
    if not retrieved_at:
        raise ValueError("Browser export is missing retrieved_at")
    catalog: list[dict] = []
    seen_products: set[str] = set()
    for page in payload.get("catalog_pages") or []:
        page_number = int(page.get("page_number") or 1)
        for rank, card in enumerate(page.get("cards") or [], 1):
            row = normalize_card(card, page_number, rank, retrieved_at)
            if row["product_id"] not in seen_products:
                catalog.append(row)
                seen_products.add(row["product_id"])
    details: list[dict] = []
    images: list[dict] = []
    for item in payload.get("product_groups") or []:
        detail, image_rows = parse_product_group(item["group"], item["source_url"], retrieved_at)
        details.append(detail)
        images.extend(image_rows)
    return catalog, details, images, list(payload.get("failures") or [])
