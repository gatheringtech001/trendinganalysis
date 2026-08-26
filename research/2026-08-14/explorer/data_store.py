from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from analysis import build_analysis
from database_builder import (
    IMAGE_ANALYSIS_DIMENSIONS, SNAPSHOT, STORES, build_database,
)
from engagement import build_engagement
from image_dimensions import build_image_dimensions
from qa_engine import answer_question


class ResearchStore:
    def __init__(self, db_path: Path):
        self.connection = sqlite3.connect(db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.image_dimension_rows_cache = None
        self.image_dimension_group_cache = {}
        self.dimension_summary_cache = {}

    def close(self) -> None:
        self.connection.close()

    def _all(self, sql: str, params=()) -> list[dict]:
        with self.lock:
            return [dict(row) for row in self.connection.execute(sql, params)]

    def _one(self, sql: str, params=()) -> dict | None:
        with self.lock:
            row = self.connection.execute(sql, params).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _decode_image_analysis(rows: list[dict]) -> list[dict]:
        for row in rows:
            tags = row.pop("analysis_tags_json", None)
            confidence = row.pop("analysis_confidence_json", None)
            version = row.pop("analysis_version", None)
            status = row.pop("analysis_status", None)
            method = row.pop("analysis_method", None)
            row["analysis"] = {
                "analysis_version": version,
                "analysis_status": status,
                "analysis_method": method,
                "tags": json.loads(tags),
                "confidence": json.loads(confidence),
            } if tags and confidence else None
        return rows

    def _where(self, store_id="", category="", query="", available=False):
        clauses, params = [], []
        if store_id in STORES:
            clauses.append("store_id = ?")
            params.append(store_id)
        if category:
            clauses.append("(category = ? COLLATE NOCASE OR category_group = ? COLLATE NOCASE)")
            params.extend([category, category])
        if query:
            clauses.append("(title LIKE ? OR product_id LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        if available:
            clauses.append("available = 1")
        return (" WHERE " + " AND ".join(clauses) if clauses else ""), params

    def summary(self, store_id="") -> dict:
        where, params = self._where(store_id=store_id)
        metrics = self._one(
            "SELECT COUNT(*) products, COALESCE(SUM(image_count),0) images, "
            "SUM(available) available, SUM(on_sale) on_sale FROM products" + where,
            params,
        )
        selected_stores = [store_id] if store_id in STORES else list(STORES)
        metrics["downloaded"] = sum(
            int(self._meta(f"downloaded:{item}")) for item in selected_stores
        )
        metrics["reviews"] = sum(
            int(self._meta(f"reviews:{item}")) for item in selected_stores
        )
        metrics["ugc"] = sum(int(self._meta(f"ugc:{item}")) for item in selected_stores)
        metrics["available_rate"] = round(
            metrics["available"] / metrics["products"], 4
        ) if metrics["products"] else 0
        categories = self._all(
            "SELECT category_group category, COUNT(*) products, SUM(image_count) images "
            "FROM products" + where + " GROUP BY category_group ORDER BY products DESC LIMIT 12",
            params,
        )
        for category in categories[:6]:
            category["stores"] = self._all(
                "SELECT store_id, COUNT(*) value FROM products WHERE category_group = ? "
                + ("AND store_id = ? " if store_id in STORES else "")
                + "GROUP BY store_id ORDER BY value DESC",
                [category["category"]] + ([store_id] if store_id in STORES else []),
            )
        return {"snapshot": SNAPSHOT, "metrics": metrics, "categories": categories}

    def _meta(self, key: str) -> str:
        row = self._one("SELECT value FROM metadata WHERE key = ?", [key])
        return row["value"] if row else "0"

    def categories(self, store_id="") -> list[dict]:
        where, params = self._where(store_id=store_id)
        return self._all(
            "SELECT category_group category, COUNT(*) products, SUM(image_count) images "
            "FROM products" + where + " GROUP BY category_group ORDER BY products DESC",
            params,
        )

    def products(self, store_id="", category="", query="", available=False,
                 page=1, page_size=24, sort="rank") -> dict:
        page, page_size = max(1, int(page)), min(60, max(1, int(page_size)))
        where, params = self._where(store_id, category, query, available)
        total = self._one("SELECT COUNT(*) total FROM products" + where, params)["total"]
        order = {
            "price_asc": "price_usd ASC", "price_desc": "price_usd DESC",
            "images": "image_count DESC", "newest": "catalog_rank ASC",
            "views": "product_detail_views DESC", "reviews": "review_count DESC",
        }.get(sort, "store_id, catalog_rank ASC")
        rows = self._all(
            "SELECT store_id, product_id, title, category, category_group, market, channel, price_usd, "
            "was_price_usd, discount_rate, available, on_sale, primary_image_url, "
            "image_count, source_url, product_detail_views, available_quantity, top_seller, "
            "estimated_sold_label, sales_is_estimated, bestseller_rank, "
            "(SELECT COUNT(*) FROM reviews r WHERE r.store_id = products.store_id "
            "AND r.product_id = products.product_id) review_count, "
            "(SELECT ROUND(AVG(rating),2) FROM reviews r WHERE r.store_id = products.store_id "
            "AND r.product_id = products.product_id) average_rating FROM products" + where
            + f" ORDER BY {order} LIMIT ? OFFSET ?",
            params + [page_size, (page - 1) * page_size],
        )
        return {"items": rows, "total": total, "page": page, "page_size": page_size}

    def images(self, store_id="", category="", query="", available=False,
               page=1, page_size=40) -> dict:
        page, page_size = max(1, int(page)), min(80, max(1, int(page_size)))
        where, params = self._where(store_id, category, query, available)
        joined = where.replace("store_id", "p.store_id").replace("category", "p.category").replace("title", "p.title").replace("product_id", "p.product_id")
        total = self._one("SELECT COUNT(*) total FROM images i JOIN products p USING(store_id, product_id)" + joined, params)["total"]
        rows = self._all(
            "SELECT i.store_id, i.product_id, i.position, i.source_url image_url, "
            "i.url_sha256, p.title, p.category, p.market, p.channel, p.price_usd, p.available, "
            "ia.analysis_version, ia.analysis_status, ia.analysis_method, "
            "ia.tags_json analysis_tags_json, ia.confidence_json analysis_confidence_json "
            "FROM images i JOIN products p USING(store_id, product_id) "
            "LEFT JOIN image_analysis ia USING(store_id, product_id, position)" + joined
            + " ORDER BY i.store_id, p.catalog_rank, i.position LIMIT ? OFFSET ?",
            params + [page_size, (page - 1) * page_size],
        )
        return {
            "items": self._decode_image_analysis(rows),
            "total": total, "page": page, "page_size": page_size,
        }

    def product_detail(self, store_id: str, product_id: str) -> dict | None:
        row = self._one("SELECT * FROM products WHERE store_id = ? AND product_id = ?", [store_id, product_id])
        if not row:
            return None
        row["sizes"] = json.loads(row.pop("sizes_json"))
        row["colours"] = json.loads(row.pop("colours_json"))
        images = self._all(
            "SELECT i.position, i.source_url, i.url_sha256, ia.analysis_version, "
            "ia.analysis_status, ia.analysis_method, ia.tags_json analysis_tags_json, "
            "ia.confidence_json analysis_confidence_json FROM images i "
            "LEFT JOIN image_analysis ia USING(store_id, product_id, position) "
            "WHERE i.store_id = ? AND i.product_id = ? ORDER BY i.position",
            [store_id, product_id],
        )
        row["images"] = self._decode_image_analysis(images)
        row["actual_sales_units"] = None
        row["actual_sales_status"] = "not_public"
        row["views_period"] = "unknown_window" if row["product_detail_views"] is not None else "not_available"
        row["review_summary"] = self._one(
            "SELECT COUNT(*) count, ROUND(AVG(rating),2) average_rating FROM reviews "
            "WHERE store_id = ? AND product_id = ?", [store_id, product_id]
        )
        row["reviews"] = self._all(
            "SELECT review_id, created_at, rating, title, content, themes_json, source_url "
            "FROM reviews WHERE store_id = ? AND product_id = ? "
            "ORDER BY created_at DESC LIMIT 8", [store_id, product_id]
        )
        return row

    def _dimension_summary(self, store_id: str) -> list[dict]:
        cache_key = store_id if store_id in STORES else ""
        if cache_key in self.dimension_summary_cache:
            return self.dimension_summary_cache[cache_key]
        where, params = (" WHERE store_id = ?", [store_id]) \
            if store_id in STORES else ("", [])
        rows = self._all(
            "SELECT dimension, COUNT(DISTINCT tag) tags, COUNT(*) assignments, "
            "COUNT(DISTINCT store_id || char(31) || product_id || char(31) || position) images "
            "FROM image_analysis_tags" + where + " GROUP BY dimension",
            params,
        )
        counts = {row["dimension"]: row for row in rows}
        summary = [
            counts.get(key, {"dimension": key, "tags": 0, "assignments": 0, "images": 0})
            for key in IMAGE_ANALYSIS_DIMENSIONS
        ]
        self.dimension_summary_cache[cache_key] = summary
        return summary

    def image_dimensions(self, store_id="", options=None) -> dict:
        return build_image_dimensions(
            self, store_id, options or {}, IMAGE_ANALYSIS_DIMENSIONS, STORES,
        )

    def engagement(self, store_id="") -> dict:
        return build_engagement(self, store_id)

    def analysis(self, store_id="") -> dict:
        return build_analysis(self, store_id)

    def answer(self, question: str) -> dict:
        return answer_question(self, question)
