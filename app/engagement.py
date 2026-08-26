from __future__ import annotations

from database_builder import SNAPSHOT, STORES


def _median(values: list[int]) -> int | None:
    if not values:
        return None
    values = sorted(values)
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    return round((values[middle - 1] + values[middle]) / 2)


def _coverage(store, store_id: str) -> dict:
    product = store._one(
        """
        SELECT COUNT(*) products,
               SUM(product_detail_views IS NOT NULL) products_with_views,
               COUNT(DISTINCT CASE WHEN product_detail_views IS NOT NULL
                    THEN COALESCE(NULLIF(handle, ''), product_id) END) unique_products_with_views,
               SUM(top_seller) top_seller_products,
               SUM(estimated_sold_label IS NOT NULL) products_with_estimated_sales,
               SUM(bestseller_rank IS NOT NULL) bestseller_products,
               SUM(available = 0) sold_out_products
        FROM products WHERE store_id = ?
        """,
        [store_id],
    )
    review = store._one(
        """
        SELECT COUNT(*) review_records,
               SUM(review_scope = 'product') product_review_records,
               SUM(review_scope = 'brand') brand_review_records,
               ROUND(AVG(rating), 2) average_rating
        FROM reviews WHERE store_id = ?
        """,
        [store_id],
    )
    family_views = store._all(
        """
        SELECT MAX(product_detail_views) value FROM products
        WHERE store_id = ? AND product_detail_views IS NOT NULL
        GROUP BY COALESCE(NULLIF(handle, ''), product_id)
        """,
        [store_id],
    )
    return {
        "store_id": store_id,
        "actual_sales_status": "not_public",
        **product,
        **review,
        "median_views": _median([row["value"] for row in family_views]),
        "views_period": "unknown_window" if product["products_with_views"] else "not_available",
        "review_scope": (
            "product" if review["product_review_records"]
            else "brand" if review["brand_review_records"]
            else "unavailable"
        ),
    }


def _view_leaders(store, selected: list[str]) -> list[dict]:
    placeholders = ",".join("?" * len(selected))
    return store._all(
        f"""
        WITH ranked AS (
            SELECT store_id, product_id, handle, title, category, price_usd,
                   product_detail_views, top_seller, available, catalog_rank,
                   primary_image_url, source_url,
                   ROW_NUMBER() OVER (
                       PARTITION BY store_id, COALESCE(NULLIF(handle, ''), product_id)
                       ORDER BY product_detail_views DESC, catalog_rank ASC
                   ) family_rank
            FROM products
            WHERE store_id IN ({placeholders}) AND product_detail_views IS NOT NULL
        )
        SELECT * FROM ranked WHERE family_rank = 1
        ORDER BY product_detail_views DESC LIMIT 12
        """,
        selected,
    )


def _review_leaders(store, selected: list[str]) -> list[dict]:
    placeholders = ",".join("?" * len(selected))
    return store._all(
        f"""
        SELECT p.store_id, p.product_id, p.title, p.category, p.price_usd,
               p.primary_image_url, p.source_url, COUNT(r.review_id) review_count,
               ROUND(AVG(r.rating), 2) average_rating
        FROM reviews r JOIN products p
          ON p.store_id = r.store_id AND p.product_id = r.product_id
        WHERE r.store_id IN ({placeholders}) AND r.review_scope = 'product'
        GROUP BY p.store_id, p.product_id
        ORDER BY review_count DESC, average_rating DESC LIMIT 12
        """,
        selected,
    )


def _sales_proxy_leaders(store, selected: list[str]) -> list[dict]:
    placeholders = ",".join("?" * len(selected))
    return store._all(
        f"""
        SELECT store_id, product_id, title, category, market, channel, price_usd,
               estimated_sold_label, sales_is_estimated, bestseller_rank,
               primary_image_url, source_url
        FROM products
        WHERE store_id IN ({placeholders}) AND estimated_sold_label IS NOT NULL
        ORDER BY CAST(REPLACE(REPLACE(estimated_sold_label, '+ sold', ''), ' sold', '') AS INTEGER) DESC,
                 COALESCE(bestseller_rank, 999999), catalog_rank LIMIT 12
        """,
        selected,
    )


def build_engagement(store, store_id: str = "") -> dict:
    selected = [store_id] if store_id in STORES else list(STORES)
    coverage = [_coverage(store, item) for item in selected]
    headline = {
        "stores_with_actual_sales": 0,
        "products_with_views": sum(row["products_with_views"] or 0 for row in coverage),
        "unique_products_with_views": sum(row["unique_products_with_views"] or 0 for row in coverage),
        "review_records": sum(row["review_records"] or 0 for row in coverage),
        "product_review_records": sum(row["product_review_records"] or 0 for row in coverage),
        "products_with_estimated_sales": sum(
            row["products_with_estimated_sales"] or 0 for row in coverage
        ),
    }
    placeholders = ",".join("?" * len(selected))
    samples = store._all(
        f"""
        SELECT store_id, review_id, review_scope, product_id, product_title, created_at, rating,
               title, SUBSTR(content, 1, 320) content, themes_json, source_url
        FROM reviews WHERE store_id IN ({placeholders})
        ORDER BY created_at DESC LIMIT 9
        """,
        selected,
    )
    return {
        "snapshot": SNAPSHOT,
        "headline": headline,
        "coverage": coverage,
        "view_leaders": _view_leaders(store, selected),
        "review_leaders": _review_leaders(store, selected),
        "sales_proxy_leaders": _sales_proxy_leaders(store, selected),
        "review_samples": samples,
        "overall_analysis": [
            {
                "title": "销量不能从公开数据直接判断",
                "finding": "四个品牌均未披露可审计的商品订单量；Aloruh(shein) 的 Estimated sold、Top Seller、站内排名和售罄只能作为销售热度代理。",
                "confidence": "High",
            },
            {
                "title": "PLT 的浏览热度可排序，但周期未知",
                "finding": "PLT 商品索引包含 product_detail_views；同款多颜色可能重复同一数值，本页已按商品族去重后排行。",
                "confidence": "High",
            },
            {
                "title": "商品级口碑目前集中在 Princess Polly",
                "finding": "Princess Polly 评论可关联具体 SKU；Motel Rocks 与 PLT 当前仅有品牌级片段，两个 Aloruh 数据源暂无公开评论记录，均不应归因到单款商品。",
                "confidence": "High",
            },
            {
                "title": "Aloruh 已按来源拆分",
                "finding": "Aloruh(shein) 只含 SHEIN SG 官方目录；Aloruh(local) 含自有站与客户本地上传数据。SG 价格、Estimated sold 与榜单只适合站内观察。",
                "confidence": "High",
            },
        ],
    }
