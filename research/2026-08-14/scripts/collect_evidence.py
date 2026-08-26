from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = ROOT / "raw"
RETRIEVED_AT = "2026-08-14T00:00:00+08:00"
WINDOW_START = "2026-05-16"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (compatible; store-research/1.0; +read-only)"})

BRANDS = {
    "princess_polly": {"name": "Princess Polly", "domain": "princesspolly.com"},
    "motel": {"name": "Motel Rocks", "domain": "motelrocks.com"},
    "prettylittlething": {"name": "PrettyLittleThing", "domain": "prettylittlething.com"},
    "aloruh": {"name": "Aloruh", "domain": "aloruh.com"},
}

QUERY_TEMPLATES = [
    "{name} official about target customer US",
    "{name} Gen Z target demographic United States",
    "{name} 2026 business performance expansion United States",
    "{name} customer reviews Trustpilot quality fit returns shipping",
    "{name} Similarweb traffic audience demographics United States",
    "site:{domain} size guide returns sustainability about",
    "{name} Instagram TikTok influencer strategy UGC 2026",
    "{name} campaign visual identity product photography 2026",
]

UGC_QUERIES = [
    "{name} outfit TikTok 2026",
    "{name} haul TikTok 2026",
    "{name} Instagram outfit 2026",
    "{name} try on haul creator",
    "{name} dress review influencer",
]


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def save_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def save_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def webiq(kind: str, query: str, limit: int) -> dict:
    key = os.environ.get("WEBIQ_API_KEY")
    if not key:
        raise RuntimeError("WEBIQ_API_KEY is required")
    cache_path = RAW / "webiq_cache" / f"{sha(kind + query + str(limit))}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    body = {"query": query, "maxResults": limit, "language": "en", "region": "US", "contentFormat": "text", "maxLength": 2200}
    for attempt in range(6):
        response = SESSION.post(f"https://api.microsoft.ai/v3/search/{kind}", headers={"x-apikey": key, "Content-Type": "application/json"}, json=body, timeout=90)
        if response.ok:
            payload = response.json()
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            time.sleep(1.2)
            return payload
        if attempt == 5:
            response.raise_for_status()
        retry_after = int(response.headers.get("Retry-After", "0") or 0)
        time.sleep(max(retry_after, 10 * (attempt + 1)))
    raise RuntimeError("unreachable")


def normalize_source(store_id: str, query: str, item: dict, kind: str, trace_id: str) -> dict:
    url = item.get("hostPageUrl") or item.get("url", "")
    content = item.get("content") or item.get("caption") or item.get("description") or ""
    return {
        "store_id": store_id, "market": "US", "source_type": f"webiq_{kind}", "query": query,
        "title": item.get("title", ""), "source_url": url, "asset_url": item.get("url") if kind == "images" else None,
        "content": content, "last_updated_at": item.get("lastUpdatedAt"), "crawled_at": item.get("crawledAt"),
        "retrieved_at": RETRIEVED_AT, "trace_id": trace_id, "content_hash": sha(url + "\n" + content),
    }


def infer_platform(url: str) -> str:
    url = url.lower()
    for platform in ("tiktok", "instagram", "youtube", "pinterest", "reddit"):
        if platform in url:
            return platform
    return "web"


def collect_webiq() -> tuple[list[dict], dict[str, list[dict]]]:
    sources: list[dict] = []
    ugc: dict[str, list[dict]] = {}
    for store_id, brand in BRANDS.items():
        for template in QUERY_TEMPLATES:
            query = template.format(**brand)
            payload = webiq("web", query, 10)
            for item in payload.get("webResults", []):
                sources.append(normalize_source(store_id, query, item, "web", payload.get("traceId", "")))
        candidates: list[dict] = []
        for template in UGC_QUERIES:
            query = template.format(**brand)
            for kind, key, limit in (("images", "imageResults", 25), ("videos", "videoResults", 15)):
                payload = webiq(kind, query, limit)
                for item in payload.get(key, []):
                    row = normalize_source(store_id, query, item, kind, payload.get("traceId", ""))
                    row["platform"] = infer_platform(row["source_url"])
                    row["within_recent_window"] = bool(row.get("last_updated_at") and row["last_updated_at"][:10] >= WINDOW_START)
                    candidates.append(row)
        unique: dict[str, dict] = {}
        for row in candidates:
            unique.setdefault(row["source_url"], row)
        ordered = sorted(unique.values(), key=lambda row: (not row["within_recent_window"], row.get("last_updated_at") or ""), reverse=False)
        ugc[store_id] = ordered[:100]
        sources.extend(ugc[store_id])
    return sources, ugc


def theme_tags(text: str) -> list[str]:
    themes = {
        "fit_size": r"\bfit|size|small|large|tight|loose\b",
        "quality": r"quality|fabric|material|seam|zip|broke|cheap",
        "shipping": r"shipping|delivery|arriv|package",
        "returns": r"return|refund|exchange",
        "style": r"cute|style|look|beautiful|gorgeous|dress",
        "occasion": r"wedding|graduation|party|vacation|festival|birthday|formal",
    }
    return [name for name, pattern in themes.items() if re.search(pattern, text, re.I)]


def collect_princess_reviews(limit: int = 500) -> list[dict]:
    sample = json.loads((DATA / "sample_princess_polly.json").read_text(encoding="utf-8"))
    products = [row for row in sample if row["sample_bucket"] == "best"] + sample
    first_page = SESSION.get(products[0]["source_url"], timeout=60).text
    match = re.search(r"staticw2\.yotpo\.com/([^/]+)/widget\.js", first_page)
    if not match:
        return []
    app_key = match.group(1)
    reviews: dict[str, dict] = {}
    for product in products:
        if len(reviews) >= limit:
            break
        url = f"https://api-cdn.yotpo.com/v1/widget/{app_key}/products/{product['product_id']}/reviews.json"
        try:
            payload = SESSION.get(url, params={"page": 1, "per_page": min(100, limit - len(reviews))}, timeout=60).json()["response"]
        except Exception:
            continue
        for review in payload.get("reviews", []):
            fields = {value.get("title"): value.get("value") for value in (review.get("custom_fields") or {}).values()}
            text = " ".join(filter(None, [review.get("title"), review.get("content")]))
            row = {
                "store_id": "princess_polly", "source_type": "official_product_review", "review_id": str(review.get("id")),
                "product_id": product["product_id"], "product_title": product["title"], "created_at": review.get("created_at"),
                "rating": review.get("score"), "title": review.get("title", ""), "content": review.get("content", ""),
                "sentiment_score": review.get("sentiment"), "verified_buyer": review.get("verified_buyer"),
                "age_bucket": fields.get("Age"), "occasion": fields.get("Occasion"), "fit": fields.get("Fit"),
                "themes": theme_tags(text), "source_url": product["source_url"], "retrieved_at": RETRIEVED_AT,
            }
            row["content_hash"] = sha(json.dumps(row, sort_keys=True, ensure_ascii=False))
            reviews[row["review_id"]] = row
            if len(reviews) >= limit:
                break
    return list(reviews.values())


def snippet_reviews(store_id: str, sources: list[dict]) -> list[dict]:
    rows = []
    for index, source in enumerate(sources):
        if source["store_id"] != store_id or "review" not in source["query"].lower():
            continue
        rows.append({"store_id": store_id, "source_type": "third_party_review_snippet", "review_id": f"snippet-{index}",
                     "created_at": source.get("last_updated_at"), "rating": None, "title": source["title"],
                     "content": source["content"], "themes": theme_tags(source["content"]),
                     "source_url": source["source_url"], "retrieved_at": RETRIEVED_AT, "content_hash": source["content_hash"]})
    return rows[:500]


def main() -> None:
    sources, ugc = collect_webiq()
    save_jsonl(DATA / "sources.jsonl", sources)
    for store_id, rows in ugc.items():
        save_json(DATA / f"ugc_{store_id}.json", rows)
    reviews = {"princess_polly": collect_princess_reviews()}
    for store_id in ("motel", "prettylittlething", "aloruh"):
        reviews[store_id] = snippet_reviews(store_id, sources)
    for store_id, rows in reviews.items():
        save_json(DATA / f"reviews_{store_id}.json", rows)
    summary = {store: {"sources": sum(row["store_id"] == store for row in sources), "ugc": len(ugc[store]), "reviews": len(reviews[store])} for store in BRANDS}
    save_json(DATA / "evidence_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
