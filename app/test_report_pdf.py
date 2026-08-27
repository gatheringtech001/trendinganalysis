import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from pypdf import PdfReader

import report_pdf
from report_pdf_layout import DeckBase
from report_pdf_insights import first_image_profile, model_profile
from report_pdf_pages import build_page_sequence
from visual_reports import PDF_NAME, SOURCE_NOTES_NAME


SECTION_COUNTS = {
    "brand_positioning": 4,
    "product_display": 3,
    "store_visual_audit": 5,
    "competitive_gap": 3,
    "visual_upgrade": 4,
}
SECTION_TITLES = {
    "brand_positioning": "品牌视觉定位校准",
    "product_display": "商品展示分析",
    "store_visual_audit": "店铺视觉审计",
    "competitive_gap": "竞品视觉差距",
    "visual_upgrade": "视觉升级方向",
}


class ReferenceReportPdfTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.image = self.root / "evidence.jpg"
        Image.new("RGB", (720, 960), "#D8C8B8").save(self.image)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _claim(section_id, index):
        prefix = f"{section_id}-{index}"
        return {
            "claim_id": prefix,
            "conclusion": f"{SECTION_TITLES[section_id]}第{index + 1}条结论。",
            "derivation": "从重点品类随机样本中归纳，并由支持图和边界反例复核。",
            "evidence": {
                "sample_count": 8,
                "filters": "全量目标图片",
                "observation_fields": ["scene", "palette"],
                "support_image_ids": [f"{prefix}-support"],
                "counterexample_image_ids": [f"{prefix}-counter"],
                "example_image_ids": [f"{prefix}-support"],
            },
        }

    @classmethod
    def report(cls):
        sections = []
        images = []
        observations = []
        competitor_stores = ["princess_polly", "motel", "prettylittlething"]
        for section_id, count in SECTION_COUNTS.items():
            claims = [cls._claim(section_id, index) for index in range(count)]
            sections.append({
                "section_id": section_id,
                "title": SECTION_TITLES[section_id],
                "summary": f"{SECTION_TITLES[section_id]}章节摘要。",
                "methodology": "重点品类随机样本逐图观察。",
                "claims": claims,
            })
            for index, claim in enumerate(claims):
                store = competitor_stores[index] if section_id == "competitive_gap" else "aloruh_shein"
                for image_id in claim["evidence"]["support_image_ids"] + claim["evidence"]["counterexample_image_ids"]:
                    is_support = image_id in claim["evidence"]["support_image_ids"]
                    if section_id == "brand_positioning" and index == 0:
                        category = "DRESSES"
                    elif section_id == "product_display" and index == 1:
                        category = "BLOUSES"
                    else:
                        category = "TOPS"
                    images.append({
                        "image_id": image_id, "store_id": store,
                        "category": category,
                        "product_id": claim["claim_id"],
                        "position": 1 if is_support else 2,
                        "resolved_url": f"https://example.com/{image_id}.jpg",
                        "selection_reasons": [
                            {"tag": "CASUAL"},
                            {"tag": "DATE_NIGHT"},
                            {"tag": "BEACH"},
                        ],
                    })
                    if category == "DRESSES":
                        framing, pose, garment = "全身全长", "正面站立", "连衣裙腰线至下摆完整"
                    elif section_id == "product_display" and index == 0:
                        framing, pose, garment = "上半身近景", "正面站立", "上衣正面局部细节"
                    elif section_id == "product_display" and index == 1:
                        if is_support:
                            framing, pose, garment = "上半身近景", "正面站立", "衬衫正面局部细节"
                        else:
                            framing, pose, garment = "背面中景", "模特背对镜头", "后背结构清楚"
                    elif section_id == "product_display" and index == 2 and not is_support:
                        framing, pose, garment = "背面中景", "人物背对镜头", "上衣背面结构清楚"
                    else:
                        framing, pose, garment = "正面中近景", "人物正面站立", "正面局部结构清楚"
                    scene = "浅灰棚拍；休闲日常通勤；浪漫约会；海边度假；夜间派对氛围"
                    if section_id == "visual_upgrade":
                        scene = "日落海滩品牌氛围场景" if index == 2 else "浅灰棚拍"
                    observations.append({
                        "image_id": image_id,
                        "observable": {
                            "scene": scene,
                            "framing": f"头部面部清楚；{framing}",
                            "pose_action": pose,
                            "silhouette": "修身廓形",
                            "design_details": "领口与腰线清楚",
                            "material_texture": "可见细腻纹理",
                            "garment_display": garment,
                            "first_image_type": "模特商品图",
                            "model_presence": "单人模特",
                            "face_visibility": "面部完整可见",
                            "hairstyle": "自然长发",
                            "makeup_presentation": "自然妆容",
                            "expression_gaze": "平静直视镜头",
                        },
                    })
        return {
            "scope": {
                "target_products": 89,
                "target_images": 60,
                "competitor_images": 97,
                "competitor_population_images": 11050,
                "categories": ["DRESSES", "TOPS", "BLOUSES"],
                "store_profile": {
                    "store_name": "Aloruh(shein)", "platform": "SHEIN SG",
                    "product_count": 2848, "image_count": 4352,
                    "market": "SG", "channel": "browser_assisted",
                    "data_updated_at": "2026-08-18",
                },
                "key_category_analysis": {
                    "distribution": [
                        {"category": "DRESSES", "products": 1159, "share": 0.4070},
                        {"category": "TOPS", "products": 561, "share": 0.1970},
                        {"category": "BLOUSES", "products": 284, "share": 0.0997},
                        {"category": "T-SHIRTS", "products": 266, "share": 0.0934},
                        {"category": "SKIRTS", "products": 126, "share": 0.0442},
                        {"category": "TWO-PIECE SETS", "products": 90, "share": 0.0316},
                        {"category": "OUTERWEAR", "products": 33, "share": 0.0116},
                        {"category": "SUITS", "products": 26, "share": 0.0091},
                        {"category": "KNIT SETS", "products": 8, "share": 0.0028},
                    ],
                    "key_categories": [
                        {"category": "DRESSES", "population_products": 1159, "sample_selected": 20},
                        {"category": "TOPS", "population_products": 561, "sample_selected": 20},
                        {"category": "BLOUSES", "population_products": 284, "sample_selected": 20},
                    ],
                    "supplementary_categories": [
                        {"category": category, "population_products": products, "sample_selected": 5}
                        for category, products in (
                            ("T-SHIRTS", 266), ("SKIRTS", 126),
                            ("TWO-PIECE SETS", 90), ("OUTERWEAR", 33),
                            ("SUITS", 26), ("KNIT SETS", 8),
                        )
                    ],
                    "sampling": {"method": "deterministic_random", "seed": "analysis-one", "sample_per_category": 20},
                    "dimension_distributions": {
                        "visual_language": [
                            {"tag": "ECOMMERCE_CLEAN", "images": 36, "share": 0.6},
                            {"tag": "LIFESTYLE", "images": 24, "share": 0.4},
                        ],
                    },
                },
                "excluded_metrics": ["CTR", "销量"],
            },
            "executive_summary": ["结论一", "结论二"],
            "competitor_evidence": {
                "stores": {
                    store: {
                        "categories": {
                            "DRESSES": {"status": "dimension_tags_unavailable"},
                            "TOPS": {"status": "available"},
                            "BLOUSES": {"status": "category_unavailable"},
                        },
                    }
                    for store in competitor_stores
                },
            },
            "sections": sections,
            "images": images,
            "image_observations": observations,
            "approved_analysis": {
                "job_id": "analysis-one",
                "review": {"approved_sections": 5, "total_sections": 5},
                "usage": {"total_tokens": 10},
                "revision_usage": None,
            },
        }

    def test_build_uses_content_driven_page_sequence(self):
        report = self.report()
        with patch("report_pdf._fetch_image", return_value=self.image):
            result = report_pdf.build_visual_report(report, self.root)

        reader = PdfReader(str(self.root / PDF_NAME))
        expected_pages = len(build_page_sequence(report))
        self.assertEqual(expected_pages, len(reader.pages))
        self.assertEqual(expected_pages, result["pages"])
        for page in reader.pages:
            self.assertEqual((1920, 1080), (int(page.mediabox.width), int(page.mediabox.height)))

        notes = json.loads((self.root / SOURCE_NOTES_NAME).read_text(encoding="utf-8"))
        layout = notes["layout_contract"]
        self.assertEqual("reference-content-driven-v4", layout["version"])
        self.assertEqual("33dcf787c9fb88ecdcd2af95add94610755b3c7aae336a21b7db4712cfcec253", layout["reference_sha256"])
        self.assertEqual([[2, "brand_positioning"], [7, "product_display"], [15, "store_visual_audit"], [26, "competitive_gap"], [36, "visual_upgrade"]], layout["section_page_order"])
        expected = {row["image_id"] for row in report["images"]}
        self.assertLessEqual(set(layout["displayed_evidence_image_ids"]), expected)
        self.assertGreater(len(layout["displayed_evidence_image_ids"]), 20)
        self.assertFalse(layout["raw_observation_index"])

    def test_page_sequence_is_not_fixed_to_reference_length(self):
        report = self.report()
        full = build_page_sequence(report)
        report["scope"]["key_category_analysis"]["key_categories"] = report[
            "scope"
        ]["key_category_analysis"]["key_categories"][:2]

        reduced = build_page_sequence(report)

        self.assertEqual(len(full) - 1, len(reduced))
        self.assertEqual(list(range(1, len(reduced) + 1)), [row["page"] for row in reduced])
        self.assertNotIn(2, [
            row.get("category_index")
            for row in reduced
            if row["kind"] == "category_sample"
        ])

        short_report = self.report()
        short_report["sections"][-1]["claims"] = short_report[
            "sections"
        ][-1]["claims"][:2]
        short_sequence = build_page_sequence(short_report)
        self.assertNotIn("PLAN B", [row["title"] for row in short_sequence])
        self.assertLess(len(short_sequence), len(full))

    def test_plan_pages_use_disjoint_claim_evidence(self):
        report = self.report()
        upgrade_claims = report["sections"][-1]["claims"]
        neutral_ids = {
            upgrade_claims[index]["evidence"]["support_image_ids"][0]
            for index in (1, 3)
        }
        atmosphere_ids = {upgrade_claims[2]["evidence"]["support_image_ids"][0]}
        unsuitable_plan_a = upgrade_claims[0]["evidence"]["support_image_ids"][0]
        fallback_scenes = ["浅灰棚拍休闲日常", "浪漫约会", "海边度假", "夜间派对"]
        for observation_index, observation in enumerate(report["image_observations"]):
            if observation["image_id"] in neutral_ids:
                observation["observable"]["scene"] = "浅灰棚拍通勤"
            elif observation["image_id"] in atmosphere_ids | {unsuitable_plan_a}:
                observation["observable"]["scene"] = "日落海滩品牌氛围场景"
                observation["observable"]["lighting"] = "夜间硬光"
            else:
                observation["observable"]["scene"] = fallback_scenes[observation_index % 4]
        with patch("report_pdf._fetch_image", return_value=self.image):
            report_pdf.build_visual_report(report, self.root)

        notes = json.loads((self.root / SOURCE_NOTES_NAME).read_text(encoding="utf-8"))
        placements = notes["layout_contract"]["page_placements"]
        plan_a = {
            row["image_id"] for row in placements if row["page_title"] == "PLAN A"
        }
        plan_b = {
            row["image_id"] for row in placements if row["page_title"] == "PLAN B"
        }
        self.assertTrue(plan_a)
        self.assertTrue(plan_b)
        self.assertFalse(plan_a & plan_b)
        self.assertNotIn(unsuitable_plan_a, plan_a)
        plan_a_text = " ".join(
            row["semantic_text"] for row in placements if row["page_title"] == "PLAN A"
        )
        plan_b_text = " ".join(
            row["semantic_text"] for row in placements if row["page_title"] == "PLAN B"
        )
        self.assertNotIn("日落海滩", plan_a_text)
        self.assertIn("浅灰棚拍", plan_a_text)
        self.assertRegex(plan_b_text, "海滩|海边|日落|街道|建筑|夜间")

    def test_pdf_uses_reference_titles_without_raw_image_index(self):
        with patch("report_pdf._fetch_image", return_value=self.image):
            report_pdf.build_visual_report(self.report(), self.root)

        text = "\n".join((page.extract_text() or "") for page in PdfReader(str(self.root / PDF_NAME)).pages)
        self.assertIn("Positioning", text)
        self.assertIn("Calibration", text)
        self.assertIn("店铺基本信息", text)
        self.assertIn("重点品类", text)
        self.assertIn("产品卖点", text)
        self.assertIn("T-SHIRTS", text)
        self.assertIn("OUTERWEAR", text)
        self.assertIn("KNIT SETS", text)
        self.assertIn("可见模特画像", text)
        self.assertIn("PRODUCT\nDISPLAY\nANALYSIS", text)
        self.assertIn("STORE\nVISUAL\nAUDIT", text)
        self.assertIn("Discrepancy", text)
        self.assertIn("Breakdown", text)
        self.assertIn("VISUAL\nUPGRADE\nDIRECTION", text)
        self.assertIn("三家竞品共同12维可比范围", text)
        self.assertIn("DRESSES / BLOUSES", text)
        self.assertNotIn("逐图观察索引", text)

    def test_product_pages_record_semantically_valid_image_placements(self):
        with patch("report_pdf._fetch_image", return_value=self.image):
            report_pdf.build_visual_report(self.report(), self.root)

        notes = json.loads((self.root / SOURCE_NOTES_NAME).read_text(encoding="utf-8"))
        placements = notes["layout_contract"]["page_placements"]
        page_nine = [row for row in placements if row["page"] == 9]
        page_ten = [row for row in placements if row["page"] == 10]
        page_eleven = [row for row in placements if row["page"] == 11]
        self.assertTrue(page_nine)
        self.assertTrue(page_ten)
        self.assertTrue(page_eleven)
        self.assertEqual({"DRESSES"}, {row["category"] for row in page_nine})
        self.assertEqual({"TOPS"}, {row["category"] for row in page_ten})
        self.assertEqual({"BLOUSES"}, {row["category"] for row in page_eleven})

        matrix = [row for row in placements if row["page_title"].startswith("每个品类固定")]
        self.assertEqual({"DRESSES", "TOPS", "BLOUSES"}, {row["category"] for row in matrix})
        for category in ("DRESSES", "TOPS", "BLOUSES"):
            self.assertTrue(any(row["slot"].startswith(category) for row in matrix))

    def test_store_level_profiles_use_counts_and_exclude_obstructed_portraits(self):
        report = self.report()
        first = first_image_profile(report)
        self.assertEqual(
            sum(1 for image in report["images"]
                if image["store_id"] == "aloruh_shein" and image["position"] == 1),
            sum(row["count"] for row in first),
        )

        target_observations = {
            row["image_id"]: row for row in report["image_observations"]
        }
        candidate = next(
            image for image in report["images"]
            if image["store_id"] == "aloruh_shein" and image["position"] == 1
        )
        target_observations[candidate["image_id"]]["observable"]["face_visibility"] = "面部大部分可见，双眼被墨镜遮挡"
        profile = model_profile(report)
        self.assertTrue(profile["rows"])
        self.assertNotIn(candidate["image_id"], profile["representative_image_ids"])
        self.assertTrue(all("/" not in row["label"] or row["denominator"] > 0 for row in profile["rows"]))

    def test_semantic_matching_rejects_negative_or_unrelated_keyword_hits(self):
        deck = DeckBase.__new__(DeckBase)
        deck.images = {
            "front": {"category": "BLOUSES", "selection_reasons": [], "title": ""},
            "back": {"category": "BLOUSES", "selection_reasons": [], "title": ""},
        }
        deck.observations = {
            "front": {"observable": {
                "pose_action": "正面站立",
                "garment_display": "正面清楚，背面不可见",
                "face_visibility": "局部侧脸可见",
                "framing": "全身",
            }},
            "back": {"observable": {
                "pose_action": "模特背对镜头",
                "garment_display": "后背结构清楚",
                "face_visibility": "局部侧脸可见",
                "framing": "后侧半身",
            }},
        }
        back_requirements = {
            "semantic_fields": ["pose_action", "framing", "garment_display"],
            "include_any": ["背面", "背对", "后侧", "后背"],
            "exclude_any": ["背面不可见", "背面不清楚", "未展示背面"],
        }
        detail_requirements = {
            "semantic_fields": ["framing", "garment_display", "design_details", "material_texture"],
            "include_any": ["局部", "近景", "特写", "近距离"],
        }

        self.assertFalse(deck._matches("front", back_requirements))
        self.assertTrue(deck._matches("back", back_requirements))
        self.assertFalse(deck._matches("back", detail_requirements))

    def test_fetch_image_reuses_report_analysis_shared_cache(self):
        source_url = "https://example.com/thumb.jpg"
        resolved_url = "https://example.com/full.jpg"
        cache_key = hashlib.sha256(f"aloruh_shein\0{source_url}".encode()).hexdigest()
        shared = self.root / "_image_cache"
        shared.mkdir()
        cached = shared / f"{cache_key}.jpg"
        cached.write_bytes(self.image.read_bytes())
        digest = hashlib.sha256(cached.read_bytes()).hexdigest()
        (shared / f"{cache_key}.json").write_text(json.dumps({
            "file": cached.name,
            "resolved_url": resolved_url,
            "width": 720,
            "height": 960,
            "bytes": cached.stat().st_size,
            "sha256": digest,
            "mime_type": "image/jpeg",
        }), encoding="utf-8")
        row = {
            "store_id": "aloruh_shein",
            "source_url": source_url,
            "resolved_url": resolved_url,
            "sha256": digest,
        }

        with patch("urllib.request.urlopen") as urlopen:
            result = report_pdf._fetch_image(row, self.root / "pdf-cache", shared)

        self.assertEqual(cached, result)
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
