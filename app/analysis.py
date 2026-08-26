from __future__ import annotations

import json
from collections import Counter

from database_builder import SNAPSHOT, STORES
from sku_matching import SKU_METHOD, build_sku_matches
from visual_analysis import (
    build_visual_profile,
    visual_comparison_insight,
    visual_comparison_rows,
)


STORE_METHODS = {
    "princess_polly": "Shopify 官方目录；商品级评论；公开 UGC 候选",
    "motel": "Shopify 官方目录；品牌级评论片段；公开 UGC 候选",
    "prettylittlething": "官方搜索索引；浏览量与 Top Seller 代理；品牌级评论片段",
    "aloruh_shein": "SHEIN SG 官方目录；150 款商品页深采；Estimated sold 仅作代理",
    "aloruh_local": "Aloruh 自有站与客户本地上传数据；客户类目沿用既有视觉分类",
}

THEME_LABELS = {
    "style": "风格/外观",
    "fit_size": "版型/尺码",
    "quality": "质量/面料",
    "occasion": "场景/活动",
    "returns": "退换货",
    "shipping": "配送",
}


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return round(ordered[middle], 2)
    return round((ordered[middle - 1] + ordered[middle]) / 2, 2)


def _ratio(value: int | float | None, total: int | float | None) -> float:
    return round((value or 0) / total, 4) if total else 0


def _categories(store, store_id: str, total: int) -> list[dict]:
    rows = store._all(
        "SELECT category_group category, COUNT(*) products FROM products "
        "WHERE store_id = ? GROUP BY category_group ORDER BY products DESC LIMIT 5",
        [store_id],
    )
    for row in rows:
        row["share"] = _ratio(row["products"], total)
    return rows


def _themes(store, store_id: str) -> list[dict]:
    counter: Counter[str] = Counter()
    for row in store._all(
        "SELECT themes_json FROM reviews WHERE store_id = ?", [store_id]
    ):
        try:
            counter.update(json.loads(row["themes_json"] or "[]"))
        except (json.JSONDecodeError, TypeError):
            continue
    return [
        {"theme": theme, "label": THEME_LABELS.get(theme, theme), "count": count}
        for theme, count in counter.most_common(6)
    ]


def _metrics(store, store_id: str) -> dict:
    product = store._one(
        """
        SELECT COUNT(*) products, SUM(available) available,
               SUM(available = 0) sold_out, SUM(on_sale) on_sale,
               SUM(image_count) images, ROUND(AVG(discount_rate), 4) avg_discount_rate,
               SUM(product_detail_views IS NOT NULL) products_with_views,
               SUM(top_seller) top_seller_products,
               SUM(estimated_sold_label IS NOT NULL) products_with_estimated_sales,
               SUM(bestseller_rank IS NOT NULL) bestseller_products
        FROM products WHERE store_id = ?
        """,
        [store_id],
    )
    review = store._one(
        """
        SELECT COUNT(*) review_records,
               SUM(review_scope = 'product') product_review_records,
               SUM(review_scope = 'brand') brand_review_records
        FROM reviews WHERE store_id = ?
        """,
        [store_id],
    )
    prices = store._all(
        "SELECT price_usd value FROM products "
        "WHERE store_id = ? AND price_usd IS NOT NULL AND price_usd > 0",
        [store_id],
    )
    unique_views = store._one(
        "SELECT COUNT(DISTINCT COALESCE(NULLIF(handle, ''), product_id)) value "
        "FROM products WHERE store_id = ? AND product_detail_views IS NOT NULL",
        [store_id],
    )["value"]
    values = [row["value"] for row in prices]
    products = product["products"] or 0
    return {
        **product,
        **review,
        "ugc_records": int(store._meta(f"ugc:{store_id}")),
        "unique_products_with_views": unique_views,
        "min_price": round(min(values), 2) if values else None,
        "median_price": _median(values),
        "max_price": round(max(values), 2) if values else None,
        "availability_rate": _ratio(product["available"], products),
        "sold_out_rate": _ratio(product["sold_out"], products),
        "sale_rate": _ratio(product["on_sale"], products),
        "images_per_product": round((product["images"] or 0) / products, 1) if products else 0,
        "review_scope": (
            "product" if review["product_review_records"]
            else "brand" if review["brand_review_records"] else "unavailable"
        ),
        "actual_sales_status": "not_public",
    }


def _evidence(metrics: dict, visual: dict) -> dict:
    if metrics["product_review_records"]:
        audience = ("Medium", "商品级评论可关联 SKU，但仍缺少可验证的人口统计与购买数据。")
    elif metrics["review_records"] or metrics["ugc_records"]:
        audience = ("Low-Medium", "仅有品牌级评论或 UGC 候选，只能发现主题，不能确认实际客群。")
    else:
        audience = ("Low", "暂无评论、UGC或公开人口统计，不能形成实际客群结论。")
    trend = (
        ("Medium", "存在同源浏览量或 Top Seller 字段，但统计窗口未知。")
        if metrics["products_with_views"] or metrics["top_seller_products"]
        or metrics["products_with_estimated_sales"]
        else ("Low", "当前只有单日目录快照，尚不能验证上新、库存或热度趋势。")
    )
    visual_note = (
        f"已对 {visual['valid_images']} 张有效主图做量化分析和接触表人工复核"
        f"（下载 {visual['sample_size']} 张）；结论不外推至全量图片。"
        if visual["valid_images"] else "尚无可分析的已下载主图样本。"
    )
    return {
        "catalog": {"confidence": "High", "note": "商品、价格、促销与可售状态来自官网公开目录。"},
        "audience": {"confidence": audience[0], "note": audience[1]},
        "visual": {"confidence": visual["confidence"], "note": visual_note},
        "trend": {"confidence": trend[0], "note": trend[1]},
    }


def _observations(store_id: str, metrics: dict, categories: list[dict]) -> list[dict]:
    top = categories[0] if categories else {"category": "未分类", "share": 0}
    fact = (
        f"目录共 {metrics['products']:,} 款；{top['category']} 占 {top['share']:.0%}；"
        f"价格中位数 ${metrics['median_price'] or 0:g}，在售率 {metrics['availability_rate']:.0%}。"
    )
    if metrics["products_with_estimated_sales"]:
        proxy = (
            f"{metrics['products_with_estimated_sales']:,} 款有 SHEIN SG Estimated sold，"
            f"{metrics['bestseller_products']:,} 款有 Bestseller 榜单；均为公开热度代理，不是真实订单量。"
        )
    elif metrics["products_with_views"]:
        proxy = (
            f"{metrics['unique_products_with_views']:,} 个商品族有公开浏览量，"
            f"{metrics['top_seller_products']:,} 条 Top Seller；周期未知，只能做同源横截面排序。"
        )
    elif metrics["product_review_records"]:
        proxy = f"{metrics['product_review_records']:,} 条商品级评论可辅助识别版型、质量和场景主题，但不能代替销量。"
    else:
        proxy = "当前没有可归因到商品的浏览量或评论热度，售罄也不能单独解释为高需求。"
    return [
        {"kind": "fact", "title": "官方目录事实", "body": fact},
        {"kind": "proxy", "title": "热度与客群代理", "body": proxy},
        {"kind": "gap", "title": "经营证据缺口", "body": "真实销量、GMV、转化、加购、复购、退货与广告效率均未公开，优化结论仍需内部数据验证。"},
    ]


def _hypotheses(metrics: dict, evidence: dict, categories: list[dict]) -> list[dict]:
    top = categories[0] if categories else {"category": "核心品类", "share": 0}
    audience_title = (
        "验证评论主题是否代表主力客群"
        if evidence["audience"]["confidence"] == "Medium"
        else "先补齐可验证的客群证据"
    )
    commercial_title = (
        "验证高促销覆盖是否依赖折扣驱动"
        if metrics["sale_rate"] >= 0.5 else "验证核心价格带与品类承接"
    )
    return [
        {"title": audience_title, "confidence": evidence["audience"]["confidence"], "evidence": evidence["audience"]["note"], "expected_impact": "提高客群判断与内容策略可信度", "validation": "仍需内部购买、转化或可验证受众数据。"},
        {"title": commercial_title, "confidence": "Medium", "evidence": f"促销覆盖 {metrics['sale_rate']:.0%}；{top['category']} 占目录 {top['share']:.0%}。", "expected_impact": "校准价格、促销和核心品类资源", "validation": "仍需内部毛利、销量和转化数据。"},
        {"title": "建立周期快照验证趋势", "confidence": "High", "evidence": "当前为单次快照，无法区分长期结构与短期变化。", "expected_impact": "识别上新、售罄、折扣和热度变化", "validation": "至少连续采集 4–8 周后再判断趋势。"},
    ]


def _profile(store, store_id: str) -> dict:
    metrics = _metrics(store, store_id)
    categories = _categories(store, store_id, metrics["products"])
    visual = build_visual_profile(store, store_id)
    evidence = _evidence(metrics, visual)
    return {
        "store_id": store_id,
        "store_name": STORES[store_id],
        "method": STORE_METHODS[store_id],
        "metrics": metrics,
        "markets": store._all(
            "SELECT market, channel, COUNT(*) products FROM products "
            "WHERE store_id = ? GROUP BY market, channel ORDER BY products DESC",
            [store_id],
        ),
        "categories": categories,
        "review_themes": _themes(store, store_id),
        "visual": visual,
        "evidence": evidence,
        "observations": _observations(store_id, metrics, categories),
        "hypotheses": _hypotheses(metrics, evidence, categories),
    }


def _comparison(store, profiles: list[dict]) -> dict:
    rows = []
    for profile in profiles:
        metrics = profile["metrics"]
        top = profile["categories"][0] if profile["categories"] else {}
        rows.append({
            "store_id": profile["store_id"], "store_name": profile["store_name"],
            "market_scope": " + ".join(sorted({row["market"] for row in profile["markets"]})),
            "products": metrics["products"], "median_price": metrics["median_price"],
            "sale_rate": metrics["sale_rate"], "availability_rate": metrics["availability_rate"],
            "images_per_product": metrics["images_per_product"], "review_records": metrics["review_records"],
            "review_scope": metrics["review_scope"], "ugc_records": metrics["ugc_records"],
            "top_category": top.get("category", "—"), "top_category_share": top.get("share", 0),
            "trend_confidence": profile["evidence"]["trend"]["confidence"],
            "audience_confidence": profile["evidence"]["audience"]["confidence"],
        })
    priced = [row for row in rows if row["median_price"] is not None]
    low, high = min(priced, key=lambda row: row["median_price"]), max(priced, key=lambda row: row["median_price"])
    promo = max(rows, key=lambda row: row["sale_rate"])
    visual = max(rows, key=lambda row: row["images_per_product"])
    insights = [
        {"title": "价格带跨度", "finding": f"目录价格中位数从 {low['store_name']} 的 ${low['median_price']:g} 到 {high['store_name']} 的 ${high['median_price']:g}。", "confidence": "High"},
        {"title": "促销覆盖", "finding": f"{promo['store_name']} 当前促销覆盖最高（{promo['sale_rate']:.0%}）；这是目录状态，不等于销售效率。", "confidence": "High"},
        {"title": "图片密度", "finding": f"{visual['store_name']} 每款平均 {visual['images_per_product']:g} 张图，为当前数据源最高；数量不代表视觉质量。", "confidence": "High"},
    ]
    visual_insight = visual_comparison_insight(profiles)
    if visual_insight:
        insights.append(visual_insight)
    return {
        "rows": rows,
        "insights": insights,
        "visual_rows": visual_comparison_rows(profiles),
        "sku_matches": build_sku_matches(store),
        "sku_method": SKU_METHOD,
        "caveats": [
            "真实销量、GMV、转化率和利润均不公开，不能据此做销售排名。",
            "目录规模差异很大；SKU 数量只能表示当前索引规模，不等于市场份额。",
            "评论口径不一致：商品级评论与品牌级片段不可直接比较数量。",
            "当前只有单次快照；除 PLT 同源热度字段外，趋势判断均需周期采集。",
            "Aloruh(shein) 为新加坡站补充渠道；价格、促销和 Estimated sold 不应与美国站点或 Aloruh(local) 做同市场成交表现比较。",
        ],
    }


def build_analysis(store, store_id: str = "") -> dict:
    selected = [store_id] if store_id in STORES else list(STORES)
    profiles = [_profile(store, item) for item in selected]
    all_profiles = profiles if not store_id else [_profile(store, item) for item in STORES]
    return {
        "snapshot": SNAPSHOT,
        "stores": profiles,
        "comparison": _comparison(store, all_profiles),
    }
