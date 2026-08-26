import sqlite3
import tempfile
import unittest
from pathlib import Path

from report_analysis_model import SECTION_IDS, observation_schema, report_schema
from report_analysis_runner import (
    COMPETITOR_BRANDS,
    SELECTION_DIMENSIONS,
    _compact_evidence,
    _select_rows,
    _validate_competitor_brand_claims,
)


class ReportAnalysisModelTest(unittest.TestCase):
    def test_observation_schema_requires_one_record_per_image(self):
        schema = observation_schema(["i1", "i2"])["schema"]
        observations = schema["properties"]["observations"]

        self.assertEqual(2, observations["minItems"])
        self.assertEqual(2, observations["maxItems"])
        self.assertEqual(
            ["i1", "i2"],
            observations["items"]["properties"]["image_id"]["enum"],
        )

    def test_report_schema_uses_the_five_reference_pdf_sections(self):
        schema = report_schema()["schema"]
        sections = schema["properties"]["sections"]

        self.assertEqual(5, sections["minItems"])
        self.assertEqual(list(SECTION_IDS), sections["items"]["properties"]["section_id"]["enum"])
        claim = sections["items"]["properties"]["claims"]["items"]
        self.assertIn("derivation", claim["required"])
        self.assertIn("counterexample_image_ids", claim["properties"]["evidence"]["required"])

    def test_competitor_evidence_uses_full_dimension_strata(self):
        with tempfile.TemporaryDirectory() as temporary:
            db_path = Path(temporary) / "selection.db"
            self._build_selection_database(db_path)

            rows, plan = _select_rows(db_path, "aloruh_shein", ["TOPS", "SKIRTS"])

        target = [row for row in rows if row["role"] == "target"]
        competitor = [row for row in rows if row["role"] == "competitor"]
        self.assertEqual(2, len(target))
        self.assertEqual(
            sum(row["selected_images"] for row in plan["stores"].values()),
            len(competitor),
        )
        self.assertEqual("dimension_stratified", plan["method"])
        self.assertEqual(list(SELECTION_DIMENSIONS), plan["dimensions"])
        for store in ("princess_polly", "motel", "prettylittlething"):
            store_plan = plan["stores"][store]
            self.assertEqual(8, store_plan["population_images"])
            self.assertEqual(8, store_plan["analyzed_images"])
            self.assertGreater(store_plan["selected_images"], 0)
            self.assertEqual(4, store_plan["categories"]["TOPS"]["population_images"])
            self.assertIn("scene", store_plan["categories"]["TOPS"]["dimensions"])
            self.assertTrue(store_plan["categories"]["TOPS"]["visual_clusters"])
        self.assertTrue(all(row["selection_reasons"] for row in competitor))
        self.assertTrue(any(
            reason["evidence_role"] == "boundary"
            for row in competitor for reason in row["selection_reasons"]
        ))
        self.assertTrue(any(
            reason.get("selection_lens") == "combined_visual_cluster"
            for row in competitor for reason in row["selection_reasons"]
        ))

    def test_competitor_evidence_rejects_incomplete_dimension_coverage(self):
        with tempfile.TemporaryDirectory() as temporary:
            db_path = Path(temporary) / "selection.db"
            self._build_selection_database(db_path, omit=("motel", "motel-tops-4", "scene"))

            with self.assertRaisesRegex(ValueError, "incomplete visual-dimension coverage"):
                _select_rows(db_path, "aloruh_shein", ["TOPS", "SKIRTS"])

    def test_synthesis_evidence_keeps_image_store_context(self):
        items = [{
            "image_id": "motel-1", "store_id": "motel", "product_id": "p1",
            "category": "TOPS", "role": "competitor",
            "selection_reasons": [{"evidence_role": "typical"}],
        }]
        batches = [{"observations": [{"image_id": "motel-1"}], "pattern_candidates": []}]

        evidence = _compact_evidence(batches, items)

        self.assertEqual("motel", evidence["image_contexts"][0]["store_id"])
        self.assertEqual("typical", evidence["image_contexts"][0]["selection_reasons"][0]["evidence_role"])

    def test_competitor_gap_requires_named_claim_with_matching_brand_image(self):
        items = []
        claims = []
        for store, label in COMPETITOR_BRANDS.items():
            image_id = f"{store}-image"
            items.append({"image_id": image_id, "store_id": store})
            claims.append({
                "conclusion": f"{label} 的商品图更强调标准棚拍",
                "derivation": f"使用 {label} 的分层证据复核",
                "evidence": {
                    "support_image_ids": [image_id], "counterexample_image_ids": [],
                    "example_image_ids": [image_id],
                },
            })
        report = {"sections": [{"section_id": "competitive_gap", "claims": claims}]}

        _validate_competitor_brand_claims(report, items)

        claims[0]["evidence"]["support_image_ids"] = ["motel-image"]
        claims[0]["evidence"]["example_image_ids"] = ["motel-image"]
        with self.assertRaisesRegex(ValueError, "Princess Polly"):
            _validate_competitor_brand_claims(report, items)

    @staticmethod
    def _build_selection_database(db_path, omit=None):
        connection = sqlite3.connect(db_path)
        connection.executescript("""
            CREATE TABLE products (
                store_id TEXT, product_id TEXT, title TEXT, category TEXT,
                category_group TEXT, catalog_rank INTEGER
            );
            CREATE TABLE images (
                store_id TEXT, product_id TEXT, position INTEGER, source_url TEXT
            );
            CREATE TABLE image_analysis_tags (
                store_id TEXT, product_id TEXT, position INTEGER,
                dimension TEXT, tag TEXT, confidence REAL
            );
        """)
        stores = ("princess_polly", "motel", "prettylittlething")
        products = [("aloruh_shein", "target-top", "TOPS", 1),
                    ("aloruh_shein", "target-skirt", "SKIRTS", 2)]
        for store in stores:
            for category in ("TOPS", "SKIRTS"):
                for index in range(1, 5):
                    products.append((store, f"{store}-{category.lower()}-{index}", category, index))
        for store, product_id, category, rank in products:
            connection.execute(
                "INSERT INTO products VALUES(?,?,?,?,?,?)",
                (store, product_id, product_id, category, category, rank),
            )
            connection.execute(
                "INSERT INTO images VALUES(?,?,1,?)",
                (store, product_id, f"https://images.example/{product_id}.jpg"),
            )
            if store == "aloruh_shein":
                continue
            index = int(product_id.rsplit("-", 1)[-1])
            for dimension in SELECTION_DIMENSIONS:
                if omit == (store, product_id, dimension):
                    continue
                tag = f"{dimension}-common" if index <= 3 else f"{dimension}-boundary"
                confidence = 0.95 if index == 1 else 0.85
                connection.execute(
                    "INSERT INTO image_analysis_tags VALUES(?,?,?,?,?,?)",
                    (store, product_id, 1, dimension, tag, confidence),
                )
        connection.commit()
        connection.close()


if __name__ == "__main__":
    unittest.main()
