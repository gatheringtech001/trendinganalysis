from __future__ import annotations

import math
import re
from collections import Counter
from itertools import combinations

from database_builder import STORES


SKU_METHOD = {
    "definition": (
        "同品类为硬条件；基础同品类 45 分、价格接近最多 25 分、"
        "标题/风格词相似最多 20 分、可用的单品热度代理最多加 10 分。"
    ),
    "scope": "每店先取最多 120 个有图、在售且价格有效的代表 SKU，再生成跨店候选对。",
    "boundary": (
        "结果仅是商品层面的候选竞品，不等于消费者实际比较、销量竞争或市场替代关系；"
        "不同店铺的浏览量、评论与 Top Seller 口径不可直接横比。"
    ),
}

STOP_WORDS = {
    "a", "and", "the", "with", "for", "in", "of", "womens", "women",
    "dress", "dresses", "top", "tops", "mini", "midi", "maxi", "shirt",
    "skirt", "trousers", "pants", "shorts", "black", "white", "red", "blue",
    "pink", "green", "grey", "gray", "brown", "beige", "navy", "cream",
}


def _tokens(title: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]+", (title or "").lower())
        if len(token) > 2 and token not in STOP_WORDS
    }


def _candidate_rows(store, store_id: str) -> list[dict]:
    rows = store._all(
        """
        SELECT p.store_id, p.product_id, p.handle, p.title,
               p.category_group category, p.price_usd, p.primary_image_url image_url,
               p.source_url, p.catalog_rank, p.product_detail_views,
               p.top_seller, COUNT(r.review_id) review_count
        FROM products p LEFT JOIN reviews r
          ON r.store_id = p.store_id AND r.product_id = p.product_id
        WHERE p.store_id = ? AND p.available = 1 AND p.price_usd > 0
          AND p.primary_image_url <> ''
        GROUP BY p.store_id, p.product_id
        ORDER BY p.top_seller DESC, COALESCE(p.product_detail_views, 0) DESC,
                 review_count DESC, COALESCE(p.catalog_rank, 999999), p.product_id
        LIMIT 360
        """,
        [store_id],
    )
    unique = []
    seen = set()
    for row in rows:
        key = row["handle"] or row["product_id"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
        if len(unique) == 120:
            break
    return unique


def _heat_score(row: dict) -> float:
    values = [1.0 if row["top_seller"] else 0.0]
    if row["product_detail_views"]:
        values.append(min(math.log1p(row["product_detail_views"]) / 12, 1))
    if row["review_count"]:
        values.append(min(math.log1p(row["review_count"]) / 5, 1))
    return max(values)


def _heat_label(row: dict) -> str:
    labels = []
    if row["top_seller"]:
        labels.append("Top Seller")
    if row["product_detail_views"]:
        labels.append(f"{row['product_detail_views']:,} 浏览（周期未知）")
    if row["review_count"]:
        labels.append(f"{row['review_count']:,} 条商品评论")
    return "；".join(labels) if labels else "无可用商品级热度代理"


def _product_payload(row: dict) -> dict:
    return {
        "store_id": row["store_id"],
        "store_name": STORES[row["store_id"]],
        "product_id": row["product_id"],
        "title": row["title"],
        "category": row["category"],
        "price_usd": row["price_usd"],
        "image_url": row["image_url"],
        "source_url": row["source_url"],
        "heat_proxy": _heat_label(row),
    }


def _score_pair(left: dict, right: dict) -> dict | None:
    if left["category"] != right["category"]:
        return None
    low, high = sorted((left["price_usd"], right["price_usd"]))
    price_similarity = low / high if high else 0
    if price_similarity < 0.4:
        return None
    left_tokens, right_tokens = _tokens(left["title"]), _tokens(right["title"])
    shared = sorted(left_tokens & right_tokens)
    union = left_tokens | right_tokens
    title_similarity = len(shared) / len(union) if union else 0
    heat_bonus = ((_heat_score(left) + _heat_score(right)) / 2) * 10
    score = round(45 + price_similarity * 25 + title_similarity * 20 + heat_bonus, 1)
    price_gap = abs(left["price_usd"] - right["price_usd"]) / high
    reasons = [f"同品类：{left['category']}", f"价格差 {price_gap:.0%}"]
    if shared:
        reasons.append("共享描述词：" + "、".join(shared[:4]))
    if heat_bonus:
        reasons.append("至少一侧存在同店热度代理")
    return {
        "score": score,
        "price_gap": round(price_gap, 4),
        "shared_tokens": shared[:6],
        "reasons": reasons,
        "left": _product_payload(left),
        "right": _product_payload(right),
    }


def _select_matches(matches: list[dict], limit: int) -> list[dict]:
    selected, use_count = [], Counter()
    for match in sorted(matches, key=lambda item: (-item["score"], item["price_gap"])):
        keys = (
            (match["left"]["store_id"], match["left"]["product_id"]),
            (match["right"]["store_id"], match["right"]["product_id"]),
        )
        if any(use_count[key] >= 2 for key in keys):
            continue
        selected.append(match)
        use_count.update(keys)
        if len(selected) == limit:
            break
    return selected


def build_sku_matches(store) -> list[dict]:
    pools = {store_id: _candidate_rows(store, store_id) for store_id in STORES}
    output = []
    for left_store, right_store in combinations(STORES, 2):
        candidates = []
        for left in pools[left_store]:
            for right in pools[right_store]:
                match = _score_pair(left, right)
                if match:
                    candidates.append(match)
        output.extend(_select_matches(candidates, 8))
    return sorted(output, key=lambda item: -item["score"])
