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
                    images.append({
                        "image_id": image_id, "store_id": store,
                        "category": "TOPS", "resolved_url": f"https://example.com/{image_id}.jpg",
                    })
                    observations.append({"image_id": image_id})
        return {
            "scope": {
                "target_images": 386,
                "competitor_images": 106,
                "competitor_population_images": 15107,
                "categories": ["TOPS", "SKIRTS"],
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
        self.assertEqual("reference-53-page-v1", layout["version"])
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
        self.assertIn("PRODUCT\nDISPLAY\nANALYSIS", text)
        self.assertIn("STORE\nVISUAL\nAUDIT", text)
        self.assertIn("Discrepancy", text)
        self.assertIn("Breakdown", text)
        self.assertIn("VISUAL\nUPGRADE\nDIRECTION", text)
        self.assertNotIn("逐图观察索引", text)


if __name__ == "__main__":
    unittest.main()
