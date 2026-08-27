import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from pypdf import PdfReader

import report_pdf
from visual_reports import PDF_NAME, SOURCE_NOTES_NAME


SECTION_COUNTS = {
    "brand_positioning": 3,
    "product_display": 3,
    "store_visual_audit": 3,
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
            "derivation": "从全量逐图观察中归纳，并由支持图和边界反例复核。",
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
                "methodology": "全量逐图观察。",
                "claims": claims,
            })
            for index, claim in enumerate(claims):
                store = competitor_stores[index] if section_id == "competitive_gap" else "aloruh_shein"
                for image_id in claim["evidence"]["support_image_ids"] + claim["evidence"]["counterexample_image_ids"]:
                    if section_id == "brand_positioning" and index == 0:
                        category = "DRESSES"
                    elif section_id == "product_display" and index == 1:
                        category = "SKIRTS"
                    else:
                        category = "TOPS"
                    images.append({
                        "image_id": image_id, "store_id": store,
                        "category": category,
                        "resolved_url": f"https://example.com/{image_id}.jpg",
                        "selection_reasons": [
                            {"tag": "CASUAL"},
                            {"tag": "DATE_NIGHT"},
                            {"tag": "BEACH"},
                        ],
                    })
                    is_support = image_id in claim["evidence"]["support_image_ids"]
                    if section_id == "product_display" and index == 0:
                        framing, pose, garment = "上半身近景", "正面站立", "上衣正面局部细节"
                    elif section_id == "product_display" and index == 1:
                        framing, pose, garment = "全身全长", "正面站立", "裙装腰头至下摆完整"
                    elif section_id == "product_display" and index == 2 and not is_support:
                        framing, pose, garment = "背面中景", "人物背对镜头", "上衣背面结构清楚"
                    else:
                        framing, pose, garment = "正面中近景", "人物正面站立", "正面局部结构清楚"
                    observations.append({
                        "image_id": image_id,
                        "observable": {
                            "scene": "休闲街头、浪漫约会、海边度假、夜间派对",
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
                "target_images": 60,
                "competitor_images": 106,
                "competitor_population_images": 15107,
                "categories": ["DRESSES", "TOPS", "SKIRTS"],
                "store_profile": {
                    "store_name": "Aloruh(shein)", "platform": "SHEIN SG",
                    "product_count": 2560, "image_count": 12000,
                    "market": "SG", "channel": "browser_assisted",
                    "data_updated_at": "2026-08-18",
                },
                "key_category_analysis": {
                    "distribution": [
                        {"category": "DRESSES", "products": 1200, "share": 0.4688},
                        {"category": "TOPS", "products": 760, "share": 0.2969},
                        {"category": "SKIRTS", "products": 340, "share": 0.1328},
                    ],
                    "key_categories": [
                        {"category": "DRESSES", "population_products": 1200, "sample_selected": 20},
                        {"category": "TOPS", "population_products": 760, "sample_selected": 20},
                        {"category": "SKIRTS", "population_products": 340, "sample_selected": 20},
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

    def test_build_is_fixed_to_reference_53_page_sequence(self):
        report = self.report()
        with patch("report_pdf._fetch_image", return_value=self.image):
            result = report_pdf.build_visual_report(report, self.root)

        reader = PdfReader(str(self.root / PDF_NAME))
        self.assertEqual(53, len(reader.pages))
        self.assertEqual(53, result["pages"])
        for page in reader.pages:
            self.assertEqual((1920, 1080), (int(page.mediabox.width), int(page.mediabox.height)))

        notes = json.loads((self.root / SOURCE_NOTES_NAME).read_text(encoding="utf-8"))
        layout = notes["layout_contract"]
        self.assertEqual("reference-53-page-v2", layout["version"])
        self.assertEqual("33dcf787c9fb88ecdcd2af95add94610755b3c7aae336a21b7db4712cfcec253", layout["reference_sha256"])
        self.assertEqual([[2, "brand_positioning"], [7, "product_display"], [15, "store_visual_audit"], [26, "competitive_gap"], [40, "visual_upgrade"]], layout["section_page_order"])
        expected = [row["image_id"] for row in report["images"]]
        self.assertCountEqual(expected, layout["displayed_evidence_image_ids"])
        self.assertFalse(layout["raw_observation_index"])

    def test_pdf_uses_reference_titles_without_raw_image_index(self):
        with patch("report_pdf._fetch_image", return_value=self.image):
            report_pdf.build_visual_report(self.report(), self.root)

        text = "\n".join((page.extract_text() or "") for page in PdfReader(str(self.root / PDF_NAME)).pages)
        self.assertIn("Positioning", text)
        self.assertIn("Calibration", text)
        self.assertIn("店铺基本信息", text)
        self.assertIn("重点品类", text)
        self.assertIn("可见模特画像", text)
        self.assertIn("PRODUCT\nDISPLAY\nANALYSIS", text)
        self.assertIn("STORE\nVISUAL\nAUDIT", text)
        self.assertIn("Discrepancy", text)
        self.assertIn("Breakdown", text)
        self.assertIn("VISUAL\nUPGRADE\nDIRECTION", text)
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
        self.assertEqual({"SKIRTS"}, {row["category"] for row in page_eleven})

        matrix = {
            row["slot"]: row
            for row in placements
            if row["page"] == 14
        }
        self.assertEqual("TOPS", matrix["TOPS 近景"]["category"])
        self.assertEqual("SKIRTS", matrix["SKIRTS 全长"]["category"])
        self.assertIn("正面", matrix["正面"]["semantic_text"])
        self.assertRegex(matrix["背面"]["semantic_text"], "背面|背对")
        self.assertRegex(matrix["局部"]["semantic_text"], "局部|近景|特写")

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
