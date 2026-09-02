import sqlite3
import tempfile
import unittest
import json
from pathlib import Path

from report_analysis_model import (
    AzureOpenAIReportAnalyzer,
    SECTION_IDS,
    _section_evidence,
    observation_schema,
    report_schema,
)
from report_analysis_runner import (
    COMPETITOR_BRANDS,
    SELECTION_DIMENSIONS,
    SUPPLEMENTARY_CATEGORIES,
    _compact_evidence,
    _analyze_image_batches,
    _select_rows,
    _validate_competitor_brand_claims,
)


class ReportAnalysisModelTest(unittest.TestCase):
    def test_report_image_batches_resume_saved_results(self):
        class Analyzer:
            def __init__(self):
                self.calls = []

            def analyze_images(self, batch):
                self.calls.append([item["image_id"] for item in batch])
                return {
                    "observations": [{"image_id": item["image_id"]} for item in batch],
                    "pattern_candidates": [],
                }

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            observations = output / "observations"
            observations.mkdir()
            items = [{"image_id": f"image-{index}"} for index in range(9)]
            saved = {
                "observations": [{"image_id": item["image_id"]} for item in items[:8]],
                "pattern_candidates": [],
            }
            (observations / "batch-0001.json").write_text(
                json.dumps(saved), encoding="utf-8",
            )
            analyzer = Analyzer()

            batches = _analyze_image_batches(
                items, analyzer, output, lambda _stage, _value: None,
                workers=2,
            )

        self.assertEqual([["image-8"]], analyzer.calls)
        self.assertEqual(2, len(batches))
        self.assertEqual("image-0", batches[0]["observations"][0]["image_id"])
        self.assertEqual("image-8", batches[1]["observations"][0]["image_id"])

    def test_observation_schema_requires_one_record_per_image(self):
        schema = observation_schema(["i1", "i2"])["schema"]
        observations = schema["properties"]["observations"]

        self.assertEqual(2, observations["minItems"])
        self.assertEqual(2, observations["maxItems"])
        self.assertEqual(
            ["i1", "i2"],
            observations["items"]["properties"]["image_id"]["enum"],
        )
        visible = observations["items"]["properties"]["observable"]
        self.assertIn("silhouette", visible["required"])
        self.assertIn("design_details", visible["required"])
        self.assertIn("material_texture", visible["required"])
        self.assertIn("hairstyle", visible["required"])
        self.assertIn("makeup_presentation", visible["required"])
        self.assertIn("face_visibility", visible["required"])

    def test_report_schema_uses_the_five_reference_pdf_sections(self):
        schema = report_schema()["schema"]
        sections = schema["properties"]["sections"]

        self.assertEqual(5, sections["minItems"])
        self.assertEqual(list(SECTION_IDS), sections["items"]["properties"]["section_id"]["enum"])
        claim = sections["items"]["properties"]["claims"]["items"]
        self.assertIn("derivation", claim["required"])
        self.assertIn("counterexample_image_ids", claim["properties"]["evidence"]["required"])

    def test_synthesis_prompt_does_not_extrapolate_target_samples_to_full_store(self):
        scope = {
            "categories": ["DRESSES", "TOPS", "BLOUSES"],
            "target_images": 60,
            "key_category_analysis": {
                "sampling": {"method": "deterministic_random", "sample_per_category": 20},
            },
        }

        prompt = AzureOpenAIReportAnalyzer._synthesis_prompt(scope)

        self.assertNotIn("目标店铺全量图片用于结论", prompt)
        self.assertIn("商品数与品类占比来自目标店铺全量目录", prompt)
        self.assertIn("视觉结论只代表重点品类的可复现随机样本", prompt)
        self.assertIn("dimension_tags_unavailable", prompt)
        self.assertIn("category_unavailable", prompt)
        self.assertIn("primary_categories", prompt)
        self.assertIn("supplementary_categories", prompt)

    def test_image_prompt_requires_observed_view_semantics(self):
        prompt = AzureOpenAIReportAnalyzer._image_prompt()

        self.assertIn("position 1与2属于同一商品", prompt)
        self.assertIn("不得仅凭图片顺序假定正面或背面", prompt)

    def test_competitor_evidence_uses_full_dimension_strata(self):
        with tempfile.TemporaryDirectory() as temporary:
            db_path = Path(temporary) / "selection.db"
            self._build_selection_database(db_path)

            rows, plan = _select_rows(db_path, "aloruh_shein", ["TOPS", "SKIRTS"])

        target = [row for row in rows if row["role"] == "target"]
        competitor = [row for row in rows if row["role"] == "competitor"]
        self.assertEqual(8, len(target))
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

    def test_auto_scope_builds_store_profile_and_reproducible_key_category_samples(self):
        with tempfile.TemporaryDirectory() as temporary:
            db_path = Path(temporary) / "selection.db"
            self._build_selection_database(db_path)

            first, plan = _select_rows(
                db_path, "aloruh_shein", None,
                key_category_limit=3, sample_per_category=2,
                sample_seed="report-seed",
            )
            second, repeated = _select_rows(
                db_path, "aloruh_shein", None,
                key_category_limit=3, sample_per_category=2,
                sample_seed="report-seed",
            )

        target = [row for row in first if row["role"] == "target"]
        self.assertEqual(
            ["DRESSES", "TOPS", "SKIRTS"],
            [row["category"] for row in plan["target"]["key_categories"]],
        )
        self.assertEqual(6, len(target))
        self.assertEqual(
            [row["product_id"] for row in target],
            [row["product_id"] for row in second if row["role"] == "target"],
        )
        self.assertEqual(plan["target"], repeated["target"])
        self.assertEqual("Aloruh(shein)", plan["target"]["store_profile"]["store_name"])
        self.assertEqual(12, plan["target"]["store_profile"]["product_count"])
        self.assertEqual(12, plan["target"]["store_profile"]["image_count"])
        self.assertEqual("deterministic_random", plan["target"]["sampling"]["method"])
        self.assertTrue(all(
            row["selection_reasons"][0]["evidence_role"] == "key_category_random_sample"
            for row in target
        ))

    def test_auto_scope_adds_whitepaper_categories_and_two_product_views(self):
        with tempfile.TemporaryDirectory() as temporary:
            db_path = Path(temporary) / "selection.db"
            self._build_selection_database(db_path)
            connection = sqlite3.connect(db_path)
            for index, category in enumerate(SUPPLEMENTARY_CATEGORIES, 1):
                product_id = f"supplementary-{index}"
                connection.execute(
                    "INSERT INTO products VALUES(?,?,?,?,?,?)",
                    ("aloruh_shein", product_id, product_id, category, category, 100 + index),
                )
                connection.execute(
                    "INSERT INTO images VALUES(?,?,1,?)",
                    ("aloruh_shein", product_id, f"https://images.example/{product_id}-1.jpg"),
                )
                connection.execute(
                    "INSERT INTO images VALUES(?,?,2,?)",
                    ("aloruh_shein", product_id, f"https://images.example/{product_id}-2.jpg"),
                )
            connection.commit()
            connection.close()

            rows, plan = _select_rows(
                db_path, "aloruh_shein", None,
                key_category_limit=3, sample_per_category=2,
                sample_seed="expanded-report",
            )

        target = [row for row in rows if row["role"] == "target"]
        supplemental = plan["target"]["supplementary_categories"]
        expected_supplementary = [
            category for category in SUPPLEMENTARY_CATEGORIES if category != "SKIRTS"
        ]
        self.assertEqual(expected_supplementary, [row["category"] for row in supplemental])
        self.assertEqual(6, len({row["product_id"] for row in target if row["product_id"].startswith("target-")}))
        self.assertTrue(all(row["sample_selected"] == 1 for row in supplemental))
        supplemental_indexes = [
            index for index, category in enumerate(SUPPLEMENTARY_CATEGORIES, 1)
            if category != "SKIRTS"
        ]
        self.assertTrue(all(
            {row["position"] for row in target if row["product_id"] == f"supplementary-{index}"} == {1, 2}
            for index in supplemental_indexes
        ))

    def test_competitor_category_without_dimension_tags_is_reported_not_inferred(self):
        with tempfile.TemporaryDirectory() as temporary:
            db_path = Path(temporary) / "selection.db"
            self._build_selection_database(db_path)
            connection = sqlite3.connect(db_path)
            connection.execute(
                "DELETE FROM image_analysis_tags WHERE store_id=? AND product_id LIKE ?",
                ("princess_polly", "princess_polly-dresses-%"),
            )
            connection.commit()
            connection.close()

            _rows, plan = _select_rows(
                db_path, "aloruh_shein", None,
                key_category_limit=3, sample_per_category=2,
                sample_seed="coverage-seed",
            )

        dresses = plan["stores"]["princess_polly"]["categories"]["DRESSES"]
        self.assertEqual("dimension_tags_unavailable", dresses["status"])
        self.assertEqual(0, dresses["analyzed_images"])
        self.assertGreater(plan["stores"]["princess_polly"]["selected_images"], 0)

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

    def test_section_evidence_filters_roles_and_observable_fields(self):
        evidence = {
            "observations": [
                {
                    "image_id": "target-1",
                    "observable": {
                        "scene": "studio", "brand_signal": "logo",
                        "material_texture": "ribbed",
                    },
                    "strengths": ["clear"], "weaknesses": ["flat"],
                    "evidence_cues": ["white backdrop"], "confidence": 0.9,
                },
                {
                    "image_id": "competitor-1",
                    "observable": {
                        "scene": "street", "brand_signal": "none",
                        "material_texture": "smooth",
                    },
                    "strengths": ["dynamic"], "weaknesses": ["busy"],
                    "evidence_cues": ["street wall"], "confidence": 0.8,
                },
            ],
            "pattern_candidates": [{
                "statement": "studio pattern",
                "support_image_ids": ["target-1", "competitor-1"],
                "counterexample_image_ids": [],
            }],
            "image_contexts": [
                {"image_id": "target-1", "role": "target", "store_id": "aloruh_shein"},
                {"image_id": "competitor-1", "role": "competitor", "store_id": "motel"},
            ],
            "competitor_evidence": {"stores": {"motel": {}}},
        }

        positioning = _section_evidence(evidence, "brand_positioning")
        competitive = _section_evidence(evidence, "competitive_gap")

        self.assertEqual(["target-1"], [row["image_id"] for row in positioning["observations"]])
        self.assertIn("brand_signal", positioning["observations"][0]["observable"])
        self.assertNotIn("material_texture", positioning["observations"][0]["observable"])
        self.assertEqual(["competitor-1"], [row["image_id"] for row in competitive["observations"]])
        self.assertEqual({"motel": {}}, competitive["competitor_evidence"]["stores"])

    def test_competitor_section_caps_cluster_detail_but_keeps_denominators(self):
        evidence = {
            "observations": [], "pattern_candidates": [], "image_contexts": [],
            "competitor_evidence": {
                "method": "dimension_stratified",
                "target": {"large": "not needed for competitor synthesis"},
                "stores": {"motel": {
                    "population_images": 1000, "analyzed_images": 900,
                    "selected_images": 20,
                    "categories": {"TOPS": {
                        "status": "available", "population_images": 600,
                        "analyzed_images": 550, "selected_images": 10,
                        "dimensions": {"scene": [{"tag": "studio", "images": 400}]},
                        "visual_clusters": [
                            {"signature": {"scene": f"scene-{index}"}, "images": 100 - index}
                            for index in range(30)
                        ],
                    }},
                }},
            },
        }

        competitive = _section_evidence(evidence, "competitive_gap")
        compact = competitive["competitor_evidence"]
        tops = compact["stores"]["motel"]["categories"]["TOPS"]

        self.assertNotIn("target", compact)
        self.assertEqual(1000, compact["stores"]["motel"]["population_images"])
        self.assertEqual(600, tops["population_images"])
        self.assertEqual(12, len(tops["visual_clusters"]))

    def test_section_synthesis_checkpoints_completed_sections(self):
        analyzer = AzureOpenAIReportAnalyzer.__new__(AzureOpenAIReportAnalyzer)
        calls = []

        def request(_content, schema, _batch_size, _max_output_tokens):
            calls.append(schema["name"])
            if schema["name"] == "report_executive_summary":
                return {"executive_summary": ["summary one", "summary two"]}
            section_id = schema["schema"]["properties"]["section_id"]["enum"][0]
            return {
                "section_id": section_id,
                "title": section_id,
                "summary": f"{section_id} summary",
                "methodology": "focused evidence",
                "claims": [],
            }

        analyzer._request = request
        evidence = {"observations": [], "pattern_candidates": [], "image_contexts": []}
        with tempfile.TemporaryDirectory() as temporary:
            checkpoint = Path(temporary)
            first = analyzer.synthesize(evidence, {}, checkpoint)
            first_calls = list(calls)
            calls.clear()
            second = analyzer.synthesize(evidence, {}, checkpoint)

        self.assertEqual(6, len(first_calls))
        self.assertEqual([], calls)
        self.assertEqual(list(SECTION_IDS), [row["section_id"] for row in first["sections"]])
        self.assertEqual(first, second)

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
        products = []
        for category, base_rank in (("DRESSES", 0), ("TOPS", 10), ("SKIRTS", 20)):
            for index in range(1, 5):
                products.append((
                    "aloruh_shein", f"target-{category.lower()}-{index}",
                    category, base_rank + index,
                ))
        for store in stores:
            for category in ("DRESSES", "TOPS", "SKIRTS"):
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
