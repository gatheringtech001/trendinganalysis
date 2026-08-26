import statistics


STORES = {
    "princess_polly": "Princess Polly",
    "motel": "Motel Rocks",
    "prettylittlething": "PrettyLittleThing",
    "aloruh_shein": "Aloruh(shein)",
    "aloruh_local": "Aloruh(local)",
}


def _rank(store, expression: str, where="", params=None) -> list[dict]:
    condition = f" WHERE {where}" if where else ""
    return store._all(
        f"SELECT store_id, {expression} value FROM products{condition} "
        "GROUP BY store_id ORDER BY value DESC",
        params or [],
    )


def _response(intent: str, rows: list[dict], label: str) -> dict:
    leader = rows[0] if rows else {"store_id": "", "value": 0}
    def display(value):
        return f"{value:,.2f}".rstrip("0").rstrip(".") if isinstance(value, float) else f"{value:,}"
    comparison = "；".join(
        f"{STORES[row['store_id']]} {display(row['value'])}" for row in rows
    )
    if intent == "median_price":
        answer = (
            f"{STORES.get(leader['store_id'], '')}价格中位数最高，为"
            f"${display(leader['value'])}。{comparison}（美元）。"
        )
    else:
        answer = (
            f"{STORES.get(leader['store_id'], '')}最多，共{display(leader['value'])}。"
            f"{comparison}。"
        )
    return {
        "supported": True,
        "intent": intent,
        "rows": rows,
        "answer": answer,
        "label": label,
        "source_id": "official_catalog",
        "confidence": "High",
    }


def answer_question(store, question: str) -> dict:
    text = question.strip().lower()
    group_map = {
        "连衣裙": "DRESSES",
        "dress": "DRESSES",
        "上衣": "TOPS",
        "半裙": "SKIRTS",
        "裙子": "SKIRTS",
        "裤": "TROUSERS",
        "泳装": "SWIMWEAR",
    }
    group = next((value for key, value in group_map.items() if key in text), None)
    if group:
        rows = _rank(store, "COUNT(*)", "category_group = ?", [group])
        return _response("category_count", rows, f"{group} SKU")
    if "图片" in text:
        return _response("image_count", _rank(store, "SUM(image_count)"), "图片索引")
    if "售罄" in text or "在售" in text:
        rows = store._all(
            "SELECT store_id, SUM(CASE WHEN available=0 THEN 1 ELSE 0 END) value, "
            "COUNT(*) total FROM products GROUP BY store_id ORDER BY value DESC"
        )
        for row in rows:
            row["rate"] = round(row["value"] / row["total"], 4)
        return _response("sold_out_rate", rows, "售罄SKU")
    if "折扣" in text or "促销" in text:
        rows = store._all(
            "SELECT store_id, SUM(on_sale) value, COUNT(*) total FROM products "
            "GROUP BY store_id ORDER BY value DESC"
        )
        for row in rows:
            row["rate"] = round(row["value"] / row["total"], 4)
        return _response("sale_rate", rows, "促销SKU")
    if "价格" in text:
        rows = []
        for store_id in STORES:
            values = [
                row["price_usd"]
                for row in store._all(
                    "SELECT price_usd FROM products WHERE store_id=? "
                    "AND price_usd IS NOT NULL ORDER BY price_usd",
                    [store_id],
                )
            ]
            value = round(statistics.median(values), 2) if values else None
            rows.append({"store_id": store_id, "value": value})
        rows.sort(key=lambda row: row["value"] or 0, reverse=True)
        return _response("median_price", rows, "价格中位数（美元）")
    if "sku" in text or "商品" in text:
        return _response("product_count", _rank(store, "COUNT(*)"), "商品SKU")
    return {
        "supported": False,
        "intent": "unsupported",
        "rows": [],
        "answer": "当前只回答SKU/分类、图片数量、价格、促销和售罄相关的可审计问题。",
        "source_id": "official_catalog",
        "confidence": "Low",
    }
