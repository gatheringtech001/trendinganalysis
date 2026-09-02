import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from analyze_explorer_images import _analyzer, load_pending, persist_results
from fashion_image_analysis import (
    ANALYSIS_VERSION,
    DIMENSIONS,
    LEGACY_ANALYSIS_VERSION,
    LEGACY_DIMENSIONS,
)


def complete_analysis():
    return {
        "analysis_version": ANALYSIS_VERSION,
        "analysis_status": "complete",
        "analysis_method": "azure_openai_visual",
        "tags": {dimension: ["UNKNOWN"] for dimension in DIMENSIONS},
        "confidence": {dimension: 0.5 for dimension in DIMENSIONS},
    }


class ExplorerAnalysisTest(unittest.TestCase):
    def test_analyzer_passes_bearer_authentication(self):
        analyzer = _analyzer(SimpleNamespace(
            endpoint="https://example.openai.azure.com/openai/v1/responses",
            api_key="token", deployment="gpt-4.1", auth_type="bearer",
        ), lambda _event: None)

        self.assertEqual("bearer", analyzer.options.auth_type)
        self.assertEqual("gpt-4.1", analyzer.options.deployment)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "explorer.db"
        connection = sqlite3.connect(self.db)
        connection.executescript("""
            CREATE TABLE products (
                store_id TEXT, product_id TEXT, title TEXT, category TEXT,
                category_group TEXT, PRIMARY KEY(store_id, product_id));
            CREATE TABLE images (
                store_id TEXT, product_id TEXT, position INTEGER, source_url TEXT,
                PRIMARY KEY(store_id, product_id, position));
            CREATE TABLE image_analysis (
                store_id TEXT, product_id TEXT, position INTEGER,
                analysis_version TEXT, analysis_status TEXT, analysis_method TEXT,
                tags_json TEXT, confidence_json TEXT,
                PRIMARY KEY(store_id, product_id, position));
            CREATE TABLE image_analysis_tags (
                store_id TEXT, product_id TEXT, position INTEGER, dimension TEXT,
                tag TEXT, confidence REAL,
                PRIMARY KEY(store_id, product_id, position, dimension, tag));
        """)
        products = [
            ("motel", "1", "Skirt one", "Skirts", "SKIRTS"),
            ("motel", "2", "Skirt two", "Skirts", "SKIRTS"),
            ("motel", "3", "Top", "Tops", "TOPS"),
        ]
        connection.executemany("INSERT INTO products VALUES(?,?,?,?,?)", products)
        images = [
            ("motel", "1", 1, "https://example.test/shared.jpg"),
            ("motel", "2", 1, "https://example.test/shared.jpg"),
            ("motel", "3", 1, "https://example.test/top.jpg"),
        ]
        connection.executemany("INSERT INTO images VALUES(?,?,?,?)", images)
        connection.commit()
        connection.close()

    def tearDown(self):
        self.temp.cleanup()

    def test_load_pending_deduplicates_urls_and_preserves_targets(self):
        pending = load_pending(self.db, "motel", "SKIRTS", 1)
        self.assertEqual(1, len(pending.requests))
        self.assertEqual(2, len(pending.targets_by_key[pending.requests[0].key]))

    def test_load_pending_reanalyzes_v1_but_skips_v2(self):
        connection = sqlite3.connect(self.db)
        legacy_tags = {dimension: ["UNKNOWN"] for dimension in LEGACY_DIMENSIONS}
        legacy_confidence = {dimension: 0.5 for dimension in LEGACY_DIMENSIONS}
        connection.execute(
            "INSERT INTO image_analysis VALUES(?,?,?,?,?,?,?,?)",
            (
                "motel", "1", 1, LEGACY_ANALYSIS_VERSION, "complete", "legacy",
                json.dumps(legacy_tags), json.dumps(legacy_confidence),
            ),
        )
        current = complete_analysis()
        connection.execute(
            "INSERT INTO image_analysis VALUES(?,?,?,?,?,?,?,?)",
            (
                "motel", "3", 1, ANALYSIS_VERSION, "complete", "current",
                json.dumps(current["tags"]), json.dumps(current["confidence"]),
            ),
        )
        connection.commit()
        connection.close()

        pending = load_pending(self.db, "motel", None, 1)

        self.assertEqual(1, len(pending.requests))
        targets = pending.targets_by_key[pending.requests[0].key]
        self.assertEqual({"1", "2"}, {target.product_id for target in targets})

    def test_persist_results_updates_database_and_source_jsonl(self):
        pending = load_pending(self.db, "motel", "SKIRTS", 1)
        analysis = complete_analysis()
        results = {pending.requests[0].key: analysis}
        images_path = self.root / "images_motel.jsonl"
        images_path.write_text("\n".join(json.dumps({
            "store_id": "motel", "product_id": product_id, "position": 1,
            "source_url": "https://example.test/shared.jpg",
        }) for product_id in ("1", "2")) + "\n", encoding="utf-8")

        persist_results(self.db, images_path, pending.targets_by_key, results)

        connection = sqlite3.connect(self.db)
        try:
            self.assertEqual(2, connection.execute(
                "SELECT COUNT(*) FROM image_analysis"
            ).fetchone()[0])
            self.assertEqual(2 * len(DIMENSIONS), connection.execute(
                "SELECT COUNT(*) FROM image_analysis_tags"
            ).fetchone()[0])
        finally:
            connection.close()
        rows = [json.loads(line) for line in images_path.read_text().splitlines()]
        self.assertTrue(all(row["analysis"] == analysis for row in rows))


if __name__ == "__main__":
    unittest.main()
