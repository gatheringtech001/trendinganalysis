"""Execute saved SQLite queries that produce every native report card, chart, and table."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
ANALYSIS = BASE / "analysis"
STORES = ["princess_polly", "motel", "prettylittlething"]


class Median:
    def __init__(self) -> None:
        self.values: list[float] = []

    def step(self, value: float | None) -> None:
        if value is not None:
            self.values.append(float(value))

    def finalize(self) -> float | None:
        values = sorted(self.values)
        if not values:
            return None
        middle = len(values) // 2
        return values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def query_text(store: str) -> str:
    return f"""-- name: summary
SELECT
  (SELECT COUNT(*) FROM catalog WHERE store_id = '{store}') AS catalog_rows,
  (SELECT MEDIAN(price_usd) FROM sample WHERE store_id = '{store}') AS sample_median_price,
  (SELECT AVG(CASE WHEN available THEN 1.0 ELSE 0.0 END) FROM sample WHERE store_id = '{store}') AS sample_available_rate,
  (SELECT COUNT(*) FROM review_theme_record WHERE store_id = '{store}' AND record_number IS NOT NULL) AS review_theme_records,
  (SELECT review_count FROM store_counts WHERE store_id = '{store}') AS review_count;

-- name: bucket_price
SELECT CASE sample_bucket WHEN 'new' THEN 'New In' WHEN 'best' THEN 'Best/Trending' ELSE 'Sale/长尾' END AS bucket,
       MEDIAN(price_usd) AS median_price_usd,
       AVG(CASE WHEN available THEN 1.0 ELSE 0.0 END) AS available_rate,
       AVG(CASE WHEN on_sale THEN 1.0 ELSE 0.0 END) AS on_sale_rate,
       COUNT(*) AS products
FROM sample WHERE store_id = '{store}'
GROUP BY sample_bucket
ORDER BY CASE sample_bucket WHEN 'new' THEN 1 WHEN 'best' THEN 2 ELSE 3 END;

-- name: categories
SELECT UPPER(TRIM(COALESCE(category, 'UNCLASSIFIED'))) AS category, COUNT(*) AS products
FROM catalog WHERE store_id = '{store}'
GROUP BY UPPER(TRIM(COALESCE(category, 'UNCLASSIFIED')))
ORDER BY products DESC LIMIT 7;

-- name: review_themes
SELECT theme, COUNT(*) AS mentions
FROM review_theme_record WHERE store_id = '{store}'
GROUP BY theme ORDER BY mentions DESC;

-- name: hypotheses
SELECT priority, hypothesis, confidence, expected_impact, validation
FROM hypothesis WHERE store_id = '{store}' ORDER BY priority;

-- name: coverage
SELECT item, actual, target, note
FROM coverage WHERE store_id = '{store}' ORDER BY item;
"""


def execute_named(connection: sqlite3.Connection, sql: str) -> dict[str, list[dict]]:
    matches = list(re.finditer(r"^-- name: ([a-z_]+)\s*$", sql, re.MULTILINE))
    result = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(sql)
        statement = sql[start:end].strip()
        result[match.group(1)] = [dict(row) for row in connection.execute(statement)]
    return result


def main() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.create_aggregate("MEDIAN", 1, Median)
    connection.executescript("""
        CREATE TABLE catalog(store_id TEXT, category TEXT, price_usd REAL, available INTEGER, on_sale INTEGER);
        CREATE TABLE sample(store_id TEXT, sample_bucket TEXT, price_usd REAL, available INTEGER, on_sale INTEGER);
        CREATE TABLE review_theme_record(store_id TEXT, record_number INTEGER, theme TEXT);
        CREATE TABLE store_counts(store_id TEXT PRIMARY KEY, review_count INTEGER);
        CREATE TABLE hypothesis(store_id TEXT, priority INTEGER, hypothesis TEXT, confidence TEXT, expected_impact TEXT, validation TEXT);
        CREATE TABLE coverage(store_id TEXT, item TEXT, actual REAL, target TEXT, note TEXT);
    """)
    report_content = load_json(ANALYSIS / "report_content.json")
    evidence = load_json(DATA / "evidence_summary.json")
    catalog_summary = load_json(DATA / "catalog_summary.json")
    for store in STORES:
        connection.executemany(
            "INSERT INTO catalog VALUES(?,?,?,?,?)",
            ((store, row.get("category"), row.get("price_usd"), bool(row.get("available")), bool(row.get("on_sale"))) for row in load_jsonl(DATA / f"catalog_{store}.jsonl")),
        )
        sample = load_json(DATA / f"sample_{store}.json")
        connection.executemany(
            "INSERT INTO sample VALUES(?,?,?,?,?)",
            ((store, row.get("sample_bucket"), row.get("price_usd"), bool(row.get("available")), bool(row.get("on_sale"))) for row in sample),
        )
        review_rows = load_json(DATA / f"reviews_{store}.json")
        connection.execute("INSERT INTO store_counts VALUES(?,?)", (store, len(review_rows)))
        connection.executemany(
            "INSERT INTO review_theme_record VALUES(?,?,?)",
            ((store, index, theme) for index, row in enumerate(review_rows, 1) for theme in row.get("themes", [])),
        )
        connection.executemany(
            "INSERT INTO hypothesis VALUES(?,?,?,?,?,?)",
            ((store, row["priority"], row["hypothesis"], row["confidence"], row["impact"], row["validation"]) for row in report_content[store]["hypotheses"]),
        )
        visual_note = "首页与列表页403，不用于视觉判断" if store == "prettylittlething" else "另含首页与New In页面视口"
        coverage = [
            ("全量目录", catalog_summary[store]["catalog_rows"], "已观察官方索引记录", "解析覆盖率100%；真实SKU总量无独立分母"),
            ("深度样本", len(sample), "150", "New/Best/Sale各50，无重复"),
            ("评论", len(review_rows), "最多500", "匿名商品评论" if store == "princess_polly" else "公开评论摘要不足，按实际交付"),
            ("UGC候选", evidence[store]["ugc"], "最多100", "近期窗口仅按可确认日期标记"),
            ("视觉样本", 24, "24张商品主图", visual_note),
        ]
        connection.executemany("INSERT INTO coverage VALUES(?,?,?,?,?)", ((store, *row) for row in coverage))
    output = {}
    for store in STORES:
        directory = BASE / "reports" / store / "queries"
        directory.mkdir(parents=True, exist_ok=True)
        sql = query_text(store)
        (directory / "report_queries.sql").write_text(sql, encoding="utf-8")
        output[store] = execute_named(connection, sql)
    target = ANALYSIS / "report_sql_output.json"
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({store: {name: len(rows) for name, rows in output[store].items()} for store in STORES}))


if __name__ == "__main__":
    main()
