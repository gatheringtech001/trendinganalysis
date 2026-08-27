import json
import tempfile
import time
import unittest
from pathlib import Path

from server import (
    AnalysisBusyError, DetailedAnalysisJobs, ReportAnalysisJobs, ResearchStore,
    VisualReportJobs, build_database,
)
from report_reviews import REPORT_SECTION_IDS, DetailedReviewStore
from report_pdf import _approval_summary
from visual_reports import VisualReportCatalog


class MatchingAnalysisStore:
    def image_dimensions(self, options=None):
        stores = (options or {}).get("stores", "motel").split(",")
        return {
            "matched_images": len(stores),
            "store_groups": [
                {
                    "store_id": store,
                    "items": [{
                        "store_id": store,
                        "product_id": f"{store}-1",
                        "position": 1,
                    }],
                }
                for store in stores
            ],
        }


class ResearchStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.data_dir = root / "data"
        self.data_dir.mkdir()
        products = {
            "princess_polly": [
                self.product("p1", "Navy Mini Dress", "Mini Dresses", 64, True, 2),
                self.product("p2", "White Top", "Knit Tops", 42, False, 1),
            ],
            "motel": [self.product("m1", "Satin Mini Dress", "Mini Dresses", 59, True, 1)],
            "prettylittlething": [
                self.product("l1", "Red Dress", "Dresses", 32, True, 3),
                self.product("l2", "Black Dress", "Dresses", 28, True, 2),
            ],
            "aloruh_shein": [self.product("a1", "Floral Maxi Dress", "Dresses", 30, True, 2)],
        }
        products["prettylittlething"][0].update(
            handle="red-dress-family", product_detail_views=1200,
            available_quantity=30, top_seller=True,
        )
        products["prettylittlething"][1].update(
            handle="red-dress-family", product_detail_views=1200,
            available_quantity=0, top_seller=False,
        )
        products["aloruh_shein"][0].update(
            market="SG", channel="shein_sg",
            estimated_sold_label="100+ sold", sales_is_estimated=True,
            bestseller_rank=2,
        )
        for store, rows in products.items():
            self.write_jsonl(self.data_dir / f"catalog_{store}.jsonl", rows)
            images = []
            for row in rows:
                for position, url in enumerate(row["image_urls"], 1):
                    images.append(
                        {
                            "store_id": store,
                            "product_id": row["product_id"],
                            "position": position,
                            "source_url": url,
                            "url_sha256": f"hash-{row['product_id']}-{position}",
                            "sample_product": False,
                        }
                    )
            self.write_jsonl(self.data_dir / f"images_{store}.jsonl", images)
        visual_features = []
        visual_values = {
            "princess_polly": (0.72, 0.24, 0.04, 0.11),
            "motel": (0.66, 0.20, 0.02, 0.09),
            "prettylittlething": (0.69, 0.27, 0.06, 0.12),
            "aloruh_shein": (0.58, 0.18, 0.10, 0.15),
        }
        for store, rows in products.items():
            for row in rows:
                brightness, saturation, warmth, edge_density = visual_values[store]
                visual_features.append({
                    "store_id": store,
                    "product_id": row["product_id"],
                    "source_url": row["primary_image_url"],
                    "content_sha256": f"content-{row['product_id']}",
                    "width": 800,
                    "height": 1200,
                    "brightness": brightness,
                    "saturation": saturation,
                    "warmth": warmth,
                    "edge_density": edge_density,
                    "border_brightness": min(brightness + 0.08, 1),
                    "border_saturation": max(saturation - 0.12, 0),
                    "dominant_family": "neutral",
                    "valid": True,
                })
        (self.data_dir / "visual_features.json").write_text(
            json.dumps(visual_features), encoding="utf-8"
        )
        reviews = {
            "princess_polly": [
                self.review("r1", "p1", 5, "版型很好"),
                self.review("r2", "p1", 4, "适合毕业活动"),
            ],
            "motel": [self.review("r3", None, None, "配送评价片段")],
            "prettylittlething": [self.review("r4", None, None, "客服评价片段")],
        }
        for store, rows in reviews.items():
            for row in rows:
                row["store_id"] = store
            (self.data_dir / f"reviews_{store}.json").write_text(
                json.dumps(rows), encoding="utf-8"
            )
        self.db_path = root / "explorer.db"
        build_database(self.db_path, self.data_dir)
        self.store = ResearchStore(self.db_path)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    @staticmethod
    def product(product_id, title, category, price, available, image_count):
        return {
            "store_id": "fixture",
            "product_id": product_id,
            "title": title,
            "category": category,
            "price_usd": price,
            "was_price_usd": price * 2,
            "discount_rate": 0.5,
            "available": available,
            "on_sale": True,
            "sizes": ["S", "M"],
            "colours": ["Black"],
            "primary_image_url": f"https://example.com/{product_id}-1.jpg",
            "image_urls": [
                f"https://example.com/{product_id}-{index}.jpg"
                for index in range(1, image_count + 1)
            ],
            "image_count": image_count,
            "source_url": f"https://example.com/products/{product_id}",
            "catalog_rank": 1,
            "retrieved_at": "2026-08-14T00:00:00+08:00",
        }

    @staticmethod
    def review(review_id, product_id, rating, content):
        return {
            "source_type": "official_product_review" if product_id else "third_party_review_snippet",
            "review_id": review_id,
            "product_id": product_id,
            "product_title": "Navy Mini Dress" if product_id else None,
            "created_at": "2026-08-01T00:00:00Z",
            "rating": rating,
            "title": "Review",
            "content": content,
            "themes": ["fit_size"],
            "source_url": "https://example.com/review",
        }

    @staticmethod
    def image_analysis():
        tags = {
            "product_category": ["DRESSES"],
            "silhouette_fit": ["FITTED"],
            "design_elements": ["RUCHED"],
            "occasion": ["DATE_NIGHT", "FORMAL"],
            "composition": ["FULL_BODY"],
            "view_action": ["STANDING"],
            "selling_points": ["WAIST"],
            "scene": ["STUDIO"],
            "material_texture": ["SATIN_LIKE"],
            "color_pattern": ["COLOR_RED", "PATTERN_SOLID"],
            "visual_language": ["EDITORIAL"],
            "styling": ["SINGLE_ITEM"],
        }
        return {
            "analysis_version": "fashion-image-v1",
            "analysis_status": "complete",
            "analysis_method": "azure_openai_visual",
            "tags": tags,
            "confidence": {dimension: 0.9 for dimension in tags},
        }

    @staticmethod
    def write_jsonl(path, rows):
        path.write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
        )

    def test_summary_reconciles_products_images_and_categories(self):
        summary = self.store.summary()
        self.assertEqual(6, summary["metrics"]["products"])
        self.assertEqual(11, summary["metrics"]["images"])
        self.assertEqual(5, summary["metrics"]["available"])
        self.assertEqual("DRESSES", summary["categories"][0]["category"])
        self.assertEqual(5, summary["categories"][0]["products"])

    def test_aloruh_sources_are_first_class_stores(self):
        shein = self.store.summary("aloruh_shein")
        local = self.store.summary("aloruh_local")
        self.assertEqual(1, shein["metrics"]["products"])
        self.assertEqual(2, shein["metrics"]["images"])
        self.assertEqual(0, local["metrics"]["products"])
        self.assertEqual(0, local["metrics"]["images"])
        engagement = self.store.engagement("aloruh_shein")
        self.assertEqual("aloruh_shein", engagement["coverage"][0]["store_id"])

    def test_customer_catalog_fragments_are_merged(self):
        official = self.product("official-1", "Aloruh official SKU", "Dresses", 30, True, 1)
        customer = self.product("customer-1", "Aloruh customer SKU", "Skirts", 0, True, 1)
        customer.update(
            price_usd=None,
            was_price_usd=None,
            source_type="customer_dataset",
            category_method="azure_openai_visual",
            category_confidence=0.92,
        )
        self.write_jsonl(self.data_dir / "catalog_aloruh.jsonl", [official])
        self.write_jsonl(
            self.data_dir / "catalog_aloruh_customer.jsonl",
            [customer],
        )
        self.write_jsonl(
            self.data_dir / "images_aloruh.jsonl",
            [{
                "store_id": "aloruh",
                "product_id": "official-1",
                "position": 1,
                "source_url": "https://example.com/official-1.jpg",
                "url_sha256": "official-image-hash",
                "sample_product": False,
            }],
        )
        self.write_jsonl(
            self.data_dir / "images_aloruh_customer.jsonl",
            [{
                "store_id": "aloruh",
                "product_id": "customer-1",
                "position": 1,
                "source_url": "https://example.com/customer-1.jpg",
                "url_sha256": "customer-image-hash",
                "sample_product": False,
                "analysis": self.image_analysis(),
            }],
        )

        customer_db = Path(self.temp.name) / "customer.db"
        build_database(customer_db, self.data_dir)
        customer_store = ResearchStore(customer_db)
        try:
            summary = customer_store.summary("aloruh_local")
            self.assertEqual(2, summary["metrics"]["products"])
            self.assertEqual(2, summary["metrics"]["images"])
            self.assertEqual(1, customer_store.categories("aloruh_local")[-1]["products"])
            self.assertEqual(1, customer_store.summary("aloruh_shein")["metrics"]["products"])
            detail = customer_store.product_detail("aloruh_local", "customer-1")
            self.assertEqual("Skirts", detail["category"])
            self.assertEqual("customer_dataset", detail["source_type"])
            self.assertEqual("azure_openai_visual", detail["category_method"])
            self.assertEqual(0.92, detail["category_confidence"])
            self.assertEqual(
                ["DATE_NIGHT", "FORMAL"],
                detail["images"][0]["analysis"]["tags"]["occasion"],
            )
            image = next(
                row for row in customer_store.images(store_id="aloruh_local")["items"]
                if row["product_id"] == "customer-1"
            )
            self.assertEqual("complete", image["analysis"]["analysis_status"])
            aggregate = customer_store.image_dimensions(
                options={
                    "filters": {"occasion": "FORMAL"},
                    "stores": "aloruh_local",
                    "images_per_store": 2,
                },
            )
            self.assertEqual(1, aggregate["analyzed_images"])
            self.assertEqual(15, len(aggregate["dimension_options"]))
            self.assertEqual([], next(
                row["tags"] for row in aggregate["dimension_options"]
                if row["dimension"] == "lighting"
            ))
            self.assertEqual(["aloruh_local"], aggregate["selected_stores"])
            self.assertEqual({"occasion": "FORMAL"}, aggregate["selected_filters"])
            self.assertEqual(1, aggregate["matched_images"])
            local_group = aggregate["store_groups"][0]
            self.assertEqual("aloruh_local", local_group["store_id"])
            self.assertEqual(1, local_group["images"])
            self.assertEqual("customer-1", local_group["items"][0]["product_id"])
            with self.assertRaises(ValueError):
                customer_store.image_dimensions(
                    options={"filters": {"not_a_dimension": "FORMAL"}},
                )
        finally:
            customer_store.close()

    def test_image_dimensions_filters_tags_with_and_and_groups_by_store(self):
        images_path = self.data_dir / "images_princess_polly.jsonl"
        images = [json.loads(line) for line in images_path.read_text(encoding="utf-8").splitlines()]
        for index, image in enumerate(images):
            analysis = self.image_analysis()
            if index == 2:
                analysis["tags"].update({
                    "product_category": ["TOPS"],
                    "occasion": ["CASUAL"],
                    "color_pattern": ["COLOR_WHITE", "PATTERN_SOLID"],
                })
            image["analysis"] = analysis
        self.write_jsonl(images_path, images)
        motel_path = self.data_dir / "images_motel.jsonl"
        motel_images = [
            json.loads(line)
            for line in motel_path.read_text(encoding="utf-8").splitlines()
        ]
        motel_images[0]["analysis"] = self.image_analysis()
        self.write_jsonl(motel_path, motel_images)

        analysis_db = Path(self.temp.name) / "image-dimensions.db"
        build_database(analysis_db, self.data_dir)
        analysis_store = ResearchStore(analysis_db)
        try:
            result = analysis_store.image_dimensions(options={
                "filters": {
                    "product_category": "DRESSES",
                    "occasion": "DATE_NIGHT",
                    "color_pattern": "PATTERN_SOLID",
                },
                "stores": "princess_polly,motel",
                "images_per_store": 2,
            })
            self.assertEqual(
                {
                    "product_category": "DRESSES",
                    "occasion": "DATE_NIGHT",
                    "color_pattern": "PATTERN_SOLID",
                },
                result["selected_filters"],
            )
            self.assertEqual(["princess_polly", "motel"], result["selected_stores"])
            self.assertEqual(4, result["analyzed_images"])
            self.assertEqual(3, result["matched_images"])
            self.assertEqual(15, len(result["dimension_options"]))
            self.assertEqual([], next(
                row["tags"] for row in result["dimension_options"]
                if row["dimension"] == "graphic_overlay"
            ))
            product_options = next(
                row for row in result["dimension_options"]
                if row["dimension"] == "product_category"
            )
            self.assertEqual(
                [{"tag": "DRESSES", "images": 3}, {"tag": "TOPS", "images": 1}],
                product_options["tags"],
            )
            by_store = {row["store_id"]: row for row in result["store_groups"]}
            self.assertEqual(2, by_store["princess_polly"]["images"])
            self.assertEqual(1, by_store["motel"]["images"])
            self.assertEqual(
                [1, 2],
                [item["position"] for item in by_store["princess_polly"]["items"]],
            )
            self.assertTrue(all(
                item["analysis"] for row in result["store_groups"] for item in row["items"]
            ))

            motel_only = analysis_store.image_dimensions(options={
                "filters": {"product_category": "DRESSES"},
                "stores": "motel",
            })
            self.assertEqual(["motel"], motel_only["selected_stores"])
            self.assertEqual(1, motel_only["analyzed_images"])
            self.assertEqual(1, motel_only["matched_images"])
            self.assertEqual(1, motel_only["store_groups"][0]["images"])

            no_filters = analysis_store.image_dimensions(options={
                "stores": "princess_polly,motel",
            })
            self.assertEqual({}, no_filters["selected_filters"])
            self.assertEqual(0, no_filters["matched_images"])
            self.assertTrue(all(row["images"] == 0 for row in no_filters["store_groups"]))

            with self.assertRaises(ValueError):
                analysis_store.image_dimensions(options={
                    "filters": {"unknown": "FORMAL"},
                })
            with self.assertRaises(ValueError):
                analysis_store.image_dimensions(options={
                    "filters": {"occasion": "NOT_A_REAL_TAG"},
                })
            with self.assertRaises(ValueError):
                analysis_store.image_dimensions(options={"filters": []})
            with self.assertRaises(ValueError):
                analysis_store.image_dimensions(options={
                    "filters": {"occasion": "FORMAL"},
                    "stores": "motel,unknown",
                })
            with self.assertRaises(ValueError):
                analysis_store.image_dimensions(options={
                    "filters": {"occasion": "FORMAL"},
                    "stores": "motel,motel",
                })
        finally:
            analysis_store.close()

    def test_detailed_analysis_job_runs_asynchronously_and_reuses_signature(self):
        output_root = Path(self.temp.name) / "detailed-jobs"

        def fake_runner(args):
            args.output.mkdir(parents=True)
            (args.output / "manifest.json").write_text(
                json.dumps({"status": "downloaded"}), encoding="utf-8",
            )
            (args.output / "result.json").write_text(json.dumps({
                "status": "complete", "filters": json.loads(args.filters),
                "stores": args.stores.split(","), "images": [],
                "analysis": {"selection_thesis": "测试结论"},
            }), encoding="utf-8")
            (args.output / "usage-summary.json").write_text(json.dumps({
                "status": "complete", "total_tokens": 123,
                "estimated_cost_usd": 0.01,
            }), encoding="utf-8")
            return args.output

        jobs = DetailedAnalysisJobs(
            MatchingAnalysisStore(), self.db_path, output_root, runner=fake_runner,
        )
        payload = {
            "filters": {"product_category": "DRESSES"},
            "stores": ["princess_polly", "motel"],
            "images_per_store": 1,
        }
        created = jobs.submit(payload)
        reused = jobs.submit(payload)
        self.assertEqual(created["job_id"], reused["job_id"])
        deadline = time.time() + 2
        status = jobs.get(created["job_id"])
        while status["status"] not in {"complete", "failed"} and time.time() < deadline:
            time.sleep(0.01)
            status = jobs.get(created["job_id"])
        self.assertEqual("complete", status["status"], status.get("error"))
        self.assertEqual("测试结论", status["result"]["analysis"]["selection_thesis"])
        self.assertEqual(123, status["usage"]["total_tokens"])

    def test_visual_report_is_absent_until_user_generates_final_pdf(self):
        pdf_dir = Path(self.temp.name) / "pdf"
        pdf_dir.mkdir()
        (pdf_dir / "Aloruh纯视觉诊断-图片结论版.pdf").write_bytes(b"%PDF-1.4\n")
        (pdf_dir / "Aloruh纯视觉诊断-图片结论版-source-notes.json").write_text(
            json.dumps({"generated": "2026-08-20", "pages": 2,
                        "aloruh_images": 2, "tops": 1, "skirts": 1}),
            encoding="utf-8",
        )

        catalog = VisualReportCatalog(
            self.db_path, pdf_dir, (), analysis_dir=self.data_dir,
        )
        self.assertEqual([], catalog.list_reports())
        final = {
            "report_id": "aloruh-visual-diagnostic-2026-08-20",
            "report_type": "final_visual", "title": "Aloruh 店铺视觉诊断",
            "generated_at": "2026-08-20T00:00:00Z", "sample_count": 2,
            "pages": 8, "sections": [{
                "section_id": "brand_positioning", "title": "品牌视觉定位校准",
                "claims": [{"claim_id": "c1", "conclusion": "结论", "derivation": "推导",
                            "evidence": {"support_image_ids": ["i1"],
                                         "counterexample_image_ids": [],
                                         "example_image_ids": ["i1"], "sample_count": 2,
                                         "filters": "首图", "observation_fields": ["场景"]}}],
            }],
        }
        (pdf_dir / "Aloruh纯视觉诊断-图片结论版.json").write_text(
            json.dumps(final), encoding="utf-8",
        )
        report = catalog.get("aloruh-visual-diagnostic-2026-08-20")

        self.assertEqual("final_visual", report["report_type"])
        self.assertEqual(2, report["sample_count"])
        for section in report["sections"]:
            for claim in section["claims"]:
                self.assertIn("derivation", claim)
                self.assertIn("support_image_ids", claim["evidence"])
                self.assertIn("counterexample_image_ids", claim["evidence"])

    def test_detailed_review_requires_suggestions_and_all_approvals(self):
        reviews = DetailedReviewStore(Path(self.temp.name) / "reviews")
        job_id = "report-analysis-one"

        with self.assertRaises(ValueError):
            reviews.save(job_id, REPORT_SECTION_IDS[0], {
                "decision": "down", "suggestion": "",
            })
        for section_id in REPORT_SECTION_IDS[:-1]:
            reviews.save(job_id, section_id, {"decision": "up"})
        pending = reviews.summary(job_id)
        self.assertFalse(pending["ready_for_final"])
        self.assertEqual(len(REPORT_SECTION_IDS) - 1, pending["approved_sections"])
        with self.assertRaises(ValueError):
            reviews.require_ready(job_id)

        complete = reviews.save(
            job_id, REPORT_SECTION_IDS[-1], {"decision": "up"},
        )
        self.assertTrue(complete["ready_for_final"])
        self.assertEqual(len(REPORT_SECTION_IDS), complete["approved_sections"])

    def test_visual_report_job_requires_approved_report_analysis(self):
        pdf_dir = Path(self.temp.name) / "generated-report"
        reviews = DetailedReviewStore(Path(self.temp.name) / "reviews")
        analysis_job_id = "report-analysis-one"
        analysis_result = {
            "scope": {"target_images": 415}, "sections": [{"section_id": "s"}],
            "images": [{"image_id": "i1"}], "executive_summary": ["测试"],
        }

        class FakeCatalog:
            def get_report_analysis(self, job_id):
                if job_id != analysis_job_id:
                    return None
                return {
                    "job_id": job_id, "status": "complete",
                    "usage": {"total_tokens": 123, "estimated_cost_usd": 0.01},
                    "revision_usage": {"total_tokens": 4, "estimated_cost_usd": 0.001},
                    "result": analysis_result,
                }

        def fake_runner(report, output_dir, progress):
            progress("rendering", 50)
            output_dir.mkdir(parents=True)
            (output_dir / "Aloruh纯视觉诊断-图片结论版.pdf").write_bytes(
                b"%PDF-1.4\n",
            )
            (output_dir / "Aloruh纯视觉诊断-图片结论版-source-notes.json").write_text(
                json.dumps({"pages": 8, "aloruh_images": report["scope"]["target_images"]}),
                encoding="utf-8",
            )
            return {"pages": 8, "sample_count": report["scope"]["target_images"]}

        jobs = VisualReportJobs(
            FakeCatalog(), pdf_dir, reviews=reviews, runner=fake_runner,
        )
        with self.assertRaises(ValueError):
            jobs.submit({"analysis_job_id": analysis_job_id})
        for section_id in REPORT_SECTION_IDS:
            reviews.save(analysis_job_id, section_id, {"decision": "up"})
        created = jobs.submit({"analysis_job_id": analysis_job_id})
        deadline = time.time() + 2
        status = jobs.get(created["job_id"])
        while status["status"] not in {"complete", "failed"} and time.time() < deadline:
            time.sleep(0.01)
            status = jobs.get(created["job_id"])

        self.assertEqual("complete", status["status"], status.get("error"))
        self.assertEqual(100, status["progress"])
        self.assertEqual(8, status["result"]["pages"])
        self.assertEqual(0, status["result"]["usage"]["total_tokens"])
        self.assertEqual(123, status["result"]["analysis_usage"]["total_tokens"])
        self.assertEqual(4, status["result"]["revision_usage"]["total_tokens"])
        self.assertTrue((pdf_dir / "Aloruh纯视觉诊断-图片结论版.pdf").is_file())
        with self.assertRaises(ValueError):
            jobs.submit({"unsupported": True})

    def test_report_analysis_requires_explicit_start_and_reanalyzes_rejected_section(self):
        root = Path(self.temp.name) / "report-analysis"
        reviews = DetailedReviewStore(Path(self.temp.name) / "reviews")
        captured = {}

        class FakeCatalog:
            @staticmethod
            def list_report_analyses():
                return []

            @staticmethod
            def get_report_analysis(_job_id):
                return None

        def fake_runner(args, progress):
            captured["args"] = args
            progress("analyzing_all_images", 70)
            args.output.mkdir(parents=True, exist_ok=True)
            result = {
                "status": "complete", "scope": {"target_images": 2},
                "executive_summary": ["测试摘要"],
                "sections": [{
                    "section_id": section_id, "title": section_id, "summary": "摘要",
                    "methodology": "逐图观察", "claims": [],
                } for section_id in REPORT_SECTION_IDS],
                "images": [{"image_id": "i1"}], "image_observations": [],
            }
            (args.output / "result.json").write_text(json.dumps(result), encoding="utf-8")
            (args.output / "usage-summary.json").write_text(
                json.dumps({"total_tokens": 100}), encoding="utf-8",
            )
            return args.output

        def fake_revision(args, progress):
            progress("revising_section", 50)
            path = args.output / "result.json"
            result = json.loads(path.read_text(encoding="utf-8"))
            for section in result["sections"]:
                if section["section_id"] == args.section_id:
                    section["summary"] = "已按建议重新分析"
            path.write_text(json.dumps(result), encoding="utf-8")
            (args.output / "revision-usage-summary.json").write_text(
                json.dumps({"total_tokens": 20}), encoding="utf-8",
            )
            return args.output

        jobs = ReportAnalysisJobs(
            FakeCatalog(), self.db_path, root, reviews,
            runner=fake_runner, revision_runner=fake_revision,
        )
        self.assertEqual([], jobs.list())
        created = jobs.submit({
            "target_store": "aloruh_shein", "category_mode": "auto",
            "key_category_limit": 3, "sample_per_category": 20,
        })
        self.assertEqual("auto", created["scope"]["category_mode"])
        self.assertEqual(3, created["scope"]["key_category_limit"])
        self.assertEqual(20, created["scope"]["sample_per_category"])
        self.assertEqual(created["job_id"], created["scope"]["sampling_seed"])
        deadline = time.time() + 2
        status = jobs.get(created["job_id"])
        while status["status"] not in {"complete", "failed"} and time.time() < deadline:
            time.sleep(0.01)
            status = jobs.get(created["job_id"])
        self.assertEqual("complete", status["status"])
        self.assertEqual(100, status["usage"]["total_tokens"])
        self.assertEqual(3, captured["args"].key_category_limit)
        self.assertEqual(20, captured["args"].sample_per_category)
        self.assertEqual(created["job_id"], captured["args"].sample_seed)

        flexible_scope = jobs._validate({
            "category_mode": "auto", "key_category_limit": 2,
        })
        self.assertEqual(2, flexible_scope["key_category_limit"])

        with self.assertRaisesRegex(ValueError, "重点品类数量"):
            jobs.submit({"category_mode": "auto", "key_category_limit": 0})
        with self.assertRaisesRegex(ValueError, "每个重点品类"):
            jobs.submit({"category_mode": "auto", "sample_per_category": 41})

        revised = jobs.revise(
            created["job_id"], REPORT_SECTION_IDS[0], "结论需要更多反例",
        )
        self.assertEqual("down", revised["review"]["sections"][REPORT_SECTION_IDS[0]]["decision"])
        deadline = time.time() + 2
        while time.time() < deadline:
            status = jobs.get(created["job_id"])
            if status.get("revision", {}).get("status") in {"complete", "failed"}:
                break
            time.sleep(0.01)
        self.assertEqual("complete", status["revision"]["status"])
        self.assertNotIn(REPORT_SECTION_IDS[0], status["review"]["sections"])
        self.assertEqual("已按建议重新分析", status["result"]["sections"][0]["summary"])
        self.assertEqual(20, status["revision_usage"]["total_tokens"])

    def test_pdf_approval_summary_uses_readable_review_counts(self):
        report = {"approved_analysis": {
            "job_id": "report-analysis-one",
            "review": {"approved_sections": 5, "total_sections": 5},
        }}

        self.assertEqual("报告专项分析 · 5/5 章节通过", _approval_summary(report))

    def test_visual_report_catalog_lists_persisted_detailed_runs(self):
        detailed_root = Path(self.temp.name) / "detailed"
        job = detailed_root / "job-one"
        job.mkdir(parents=True)
        (job / "result.json").write_text(json.dumps({
            "status": "complete", "filters": {"product_category": "TOPS"},
            "stores": ["motel"], "images": [],
            "analysis": {"selection_thesis": "测试精细结论"},
        }), encoding="utf-8")
        (job / "usage-summary.json").write_text(
            json.dumps({"total_tokens": 12}), encoding="utf-8",
        )

        rows = VisualReportCatalog(
            self.db_path, Path(self.temp.name) / "pdf", (detailed_root,),
            analysis_dir=self.data_dir,
        ).list_detailed()

        self.assertEqual("job-one", rows[0]["job_id"])
        self.assertEqual("测试精细结论", rows[0]["result"]["analysis"]["selection_thesis"])

    def test_detailed_analysis_job_rejects_invalid_or_competing_requests(self):
        def slow_runner(args):
            time.sleep(0.15)
            args.output.mkdir(parents=True)
            (args.output / "result.json").write_text(
                json.dumps({"status": "complete", "analysis": {}}), encoding="utf-8",
            )
            return args.output

        jobs = DetailedAnalysisJobs(
            MatchingAnalysisStore(), self.db_path,
            Path(self.temp.name) / "jobs", runner=slow_runner,
        )
        with self.assertRaises(ValueError):
            jobs.submit({"filters": {}, "stores": ["motel"], "images_per_store": 1})
        with self.assertRaises(ValueError):
            jobs.submit({
                "filters": {"product_category": "DRESSES"},
                "stores": ["motel"], "images_per_store": 9,
            })
        jobs.submit({
            "filters": {"product_category": "DRESSES"},
            "stores": ["motel"], "images_per_store": 1,
        })
        with self.assertRaises(AnalysisBusyError):
            jobs.submit({
                "filters": {"product_category": "DRESSES"},
                "stores": ["princess_polly"], "images_per_store": 1,
            })

    def test_detailed_analysis_job_accepts_only_visible_manual_selection(self):
        captured = {}

        def fake_runner(args):
            captured["selected_images"] = json.loads(args.selected_images)
            args.output.mkdir(parents=True)
            (args.output / "result.json").write_text(
                json.dumps({"status": "complete", "analysis": {}}), encoding="utf-8",
            )
            return args.output

        jobs = DetailedAnalysisJobs(
            MatchingAnalysisStore(), self.db_path,
            Path(self.temp.name) / "manual-jobs", runner=fake_runner,
        )
        selection = [{
            "store_id": "motel", "product_id": "motel-1", "position": 1,
        }]
        created = jobs.submit({
            "filters": {"product_category": "DRESSES"},
            "stores": ["motel"],
            "selected_images": selection,
        })
        deadline = time.time() + 2
        status = jobs.get(created["job_id"])
        while status["status"] not in {"complete", "failed"} and time.time() < deadline:
            time.sleep(0.01)
            status = jobs.get(created["job_id"])
        self.assertEqual("complete", status["status"])
        self.assertEqual(selection, captured["selected_images"])
        self.assertEqual("manual", status["selection_mode"])

        with self.assertRaisesRegex(ValueError, "displayed filtered results"):
            jobs.submit({
                "filters": {"product_category": "DRESSES"},
                "stores": ["motel"],
                "selected_images": [{
                    "store_id": "motel", "product_id": "not-visible", "position": 1,
                }],
            })

    def test_product_filters_and_detail_images(self):
        result = self.store.products(
            store_id="princess_polly", category="Mini Dresses", query="navy"
        )
        self.assertEqual(1, result["total"])
        self.assertEqual("p1", result["items"][0]["product_id"])
        detail = self.store.product_detail("princess_polly", "p1")
        self.assertEqual(2, len(detail["images"]))

    def test_store_summary_and_image_pagination(self):
        summary = self.store.summary("motel")
        self.assertEqual(1, summary["metrics"]["products"])
        self.assertEqual(1, summary["metrics"]["images"])
        images = self.store.images(store_id="prettylittlething", page_size=2)
        self.assertEqual(5, images["total"])
        self.assertEqual(2, len(images["items"]))
        available_images = self.store.images(
            store_id="princess_polly", available=True, page_size=10
        )
        self.assertEqual(2, available_images["total"])

    def test_database_dedupes_shared_image_urls_per_store(self):
        products = [
            self.product("shared-1", "Shared One", "Dresses", 30, True, 1),
            self.product("shared-2", "Shared Two", "Dresses", 32, True, 1),
        ]
        shared_url = products[0]["primary_image_url"]
        products[1]["primary_image_url"] = shared_url
        products[1]["image_urls"] = [shared_url]
        self.write_jsonl(
            self.data_dir / "catalog_aloruh_shein.jsonl", products,
        )
        self.write_jsonl(
            self.data_dir / "images_aloruh_shein.jsonl",
            [
                {
                    "product_id": row["product_id"],
                    "position": 1,
                    "source_url": shared_url,
                    "url_sha256": "shared-hash",
                    "sample_product": False,
                }
                for row in products
            ],
        )
        deduped_db = Path(self.temp.name) / "deduped.db"
        build_database(deduped_db, self.data_dir)
        deduped_store = ResearchStore(deduped_db)
        try:
            summary = deduped_store.summary("aloruh_shein")
            images = deduped_store.images(store_id="aloruh_shein")
            self.assertEqual(1, summary["metrics"]["images"])
            self.assertEqual(1, images["total"])
            self.assertEqual(1, len({row["image_url"] for row in images["items"]}))
        finally:
            deduped_store.close()

    def test_question_answer_is_deterministic_and_sourced(self):
        answer = self.store.answer("哪家店的连衣裙SKU最多？")
        self.assertTrue(answer["supported"])
        self.assertEqual("prettylittlething", answer["rows"][0]["store_id"])
        self.assertEqual(2, answer["rows"][0]["value"])
        self.assertEqual("official_catalog", answer["source_id"])

    def test_unknown_question_fails_explicitly(self):
        answer = self.store.answer("明年应该投资什么风格？")
        self.assertFalse(answer["supported"])
        self.assertEqual("unsupported", answer["intent"])

    def test_engagement_separates_actual_sales_views_and_review_scope(self):
        result = self.store.engagement()
        self.assertEqual(0, result["headline"]["stores_with_actual_sales"])
        self.assertEqual(2, result["headline"]["products_with_views"])
        self.assertEqual(4, result["headline"]["review_records"])
        self.assertEqual(2, result["headline"]["product_review_records"])
        self.assertEqual(1, result["headline"]["products_with_estimated_sales"])
        plt = next(row for row in result["coverage"] if row["store_id"] == "prettylittlething")
        aloruh = next(row for row in result["coverage"] if row["store_id"] == "aloruh_shein")
        self.assertEqual("not_public", plt["actual_sales_status"])
        self.assertEqual(1, plt["unique_products_with_views"])
        self.assertEqual(1, plt["top_seller_products"])
        self.assertEqual(1, aloruh["products_with_estimated_sales"])
        self.assertEqual(1, len(result["view_leaders"]))
        self.assertEqual("a1", result["sales_proxy_leaders"][0]["product_id"])

    def test_product_detail_contains_engagement_and_product_reviews(self):
        detail = self.store.product_detail("princess_polly", "p1")
        self.assertEqual("not_public", detail["actual_sales_status"])
        self.assertEqual(2, detail["review_summary"]["count"])
        self.assertEqual(4.5, detail["review_summary"]["average_rating"])
        self.assertEqual(2, len(detail["reviews"]))
        plt = self.store.product_detail("prettylittlething", "l1")
        self.assertEqual(1200, plt["product_detail_views"])
        self.assertEqual("unknown_window", plt["views_period"])

    def test_product_sales_proxy_preserves_market_and_channel(self):
        products = self.store.products(store_id="aloruh_shein")
        self.assertEqual("SG", products["items"][0]["market"])
        self.assertEqual("shein_sg", products["items"][0]["channel"])
        self.assertEqual("100+ sold", products["items"][0]["estimated_sold_label"])
        detail = self.store.product_detail("aloruh_shein", "a1")
        self.assertTrue(detail["sales_is_estimated"])
        self.assertEqual(2, detail["bestseller_rank"])

    def test_products_sort_by_views_and_reviews(self):
        viewed = self.store.products(store_id="prettylittlething", sort="views")
        reviewed = self.store.products(store_id="princess_polly", sort="reviews")
        self.assertEqual("l1", viewed["items"][0]["product_id"])
        self.assertEqual(2, reviewed["items"][0]["review_count"])

    def test_store_analysis_separates_facts_proxies_and_gaps(self):
        result = self.store.analysis("aloruh_shein")
        self.assertEqual(1, len(result["stores"]))
        profile = result["stores"][0]
        self.assertEqual("aloruh_shein", profile["store_id"])
        self.assertEqual(1, profile["metrics"]["products"])
        self.assertEqual(2.0, profile["metrics"]["images_per_product"])
        self.assertEqual(30, profile["metrics"]["median_price"])
        self.assertEqual("Low", profile["evidence"]["audience"]["confidence"])
        self.assertEqual("not_public", profile["metrics"]["actual_sales_status"])
        self.assertEqual(1, profile["metrics"]["products_with_estimated_sales"])
        self.assertEqual("Medium", profile["evidence"]["trend"]["confidence"])
        self.assertIn("Estimated sold", profile["observations"][1]["body"])
        self.assertEqual({"fact", "proxy", "gap"}, {
            item["kind"] for item in profile["observations"]
        })

    def test_competitor_analysis_uses_comparable_snapshot_metrics(self):
        result = self.store.analysis()
        self.assertEqual(5, len(result["stores"]))
        self.assertEqual(5, len(result["comparison"]["rows"]))
        plt = next(
            item for item in result["stores"]
            if item["store_id"] == "prettylittlething"
        )
        princess = next(
            item for item in result["stores"]
            if item["store_id"] == "princess_polly"
        )
        self.assertEqual("Medium", plt["evidence"]["trend"]["confidence"])
        self.assertEqual(1, plt["metrics"]["top_seller_products"])
        self.assertEqual("product", princess["metrics"]["review_scope"])
        self.assertIn("真实销量", result["comparison"]["caveats"][0])

    def test_store_analysis_includes_auditable_visual_sample(self):
        profile = self.store.analysis("princess_polly")["stores"][0]
        visual = profile["visual"]
        self.assertEqual(2, visual["sample_size"])
        self.assertEqual(2, visual["valid_images"])
        self.assertAlmostEqual(0.72, visual["metrics"]["brightness"])
        self.assertEqual("Low", visual["confidence"])
        self.assertIn("构图", visual["manual_review"])
        self.assertIn("2 张", profile["evidence"]["visual"]["note"])

    def test_competitor_analysis_returns_explainable_sku_candidates(self):
        comparison = self.store.analysis()["comparison"]
        self.assertEqual(5, len(comparison["visual_rows"]))
        self.assertGreater(len(comparison["sku_matches"]), 0)
        match = comparison["sku_matches"][0]
        self.assertNotEqual(match["left"]["store_id"], match["right"]["store_id"])
        self.assertEqual(match["left"]["category"], match["right"]["category"])
        self.assertGreaterEqual(match["score"], 0)
        self.assertTrue(match["reasons"])
        self.assertIn("同品类", comparison["sku_method"]["definition"])


if __name__ == "__main__":
    unittest.main()
