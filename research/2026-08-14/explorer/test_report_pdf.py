import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from pypdf import PdfReader

import report_pdf
from visual_reports import PDF_NAME, SOURCE_NOTES_NAME


class EditorialReportPdfTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.image = self.root / "evidence.jpg"
        Image.new("RGB", (720, 960), "#D8C8B8").save(self.image)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def report():
        return {
            "scope": {
                "target_images": 2,
                "competitor_images": 0,
                "competitor_population_images": 0,
                "categories": ["TOPS", "SKIRTS"],
                "excluded_metrics": ["CTR", "销量"],
            },
            "executive_summary": ["结论一", "结论二"],
            "sections": [{
                "section_id": "brand_positioning",
                "title": "品牌视觉定位校准",
                "summary": "将零散风格收束为可识别的品牌视觉系统。",
                "methodology": "全量逐图观察，并用代表图和边界反例复核。",
                "claims": [{
                    "conclusion": "浪漫度假与夜间外出是最稳定的视觉方向。",
                    "derivation": "从场景、配色、造型与商品展示字段交叉归纳。",
                    "evidence": {
                        "sample_count": 2,
                        "filters": "target_store=aloruh_shein",
                        "observation_fields": ["scene", "palette"],
                        "support_image_ids": ["support-1"],
                        "counterexample_image_ids": ["counter-1"],
                        "example_image_ids": ["support-1", "counter-1"],
                    },
                }],
            }],
            "images": [
                {"image_id": "support-1", "store_id": "aloruh_shein",
                 "category": "TOPS", "resolved_url": "https://example.com/one.jpg"},
                {"image_id": "counter-1", "store_id": "aloruh_shein",
                 "category": "SKIRTS", "resolved_url": "https://example.com/two.jpg"},
            ],
            "image_observations": [
                {"image_id": "support-1", "strengths": ["商品结构清晰"],
                 "weaknesses": [], "evidence_cues": ["背景统一"]},
                {"image_id": "counter-1", "strengths": [],
                 "weaknesses": ["场景分散注意"], "evidence_cues": ["背景元素过多"]},
            ],
            "approved_analysis": {
                "job_id": "analysis-one",
                "review": {"approved_sections": 5, "total_sections": 5},
                "usage": {"total_tokens": 10},
                "revision_usage": None,
            },
        }

    def test_build_matches_reference_canvas_and_displays_every_evidence_image(self):
        with patch("report_pdf._fetch_image", return_value=self.image):
            result = report_pdf.build_visual_report(self.report(), self.root)

        reader = PdfReader(str(self.root / PDF_NAME))
        page = reader.pages[0].mediabox
        self.assertEqual((1920, 1080), (int(page.width), int(page.height)))
        self.assertEqual(len(reader.pages), result["pages"])

        notes = json.loads((self.root / SOURCE_NOTES_NAME).read_text(encoding="utf-8"))
        layout = notes["layout_contract"]
        self.assertEqual("editorial-image-first-v1", layout["version"])
        self.assertEqual(
            "33dcf787c9fb88ecdcd2af95add94610755b3c7aae336a21b7db4712cfcec253",
            layout["reference_sha256"],
        )
        self.assertCountEqual(
            ["support-1", "counter-1"], layout["displayed_evidence_image_ids"],
        )
        self.assertFalse(layout["raw_observation_index"])

    def test_pdf_uses_editorial_pages_instead_of_raw_observation_rows(self):
        with patch("report_pdf._fetch_image", return_value=self.image):
            report_pdf.build_visual_report(self.report(), self.root)

        text = "\n".join(
            (page.extract_text() or "")
            for page in PdfReader(str(self.root / PDF_NAME)).pages
        )
        self.assertNotIn("逐图观察索引", text)
        self.assertIn("VISUAL POSITIONING", text)
        self.assertIn("支持证据", text)
        self.assertIn("边界反例", text)


if __name__ == "__main__":
    unittest.main()
