import json
import tempfile
from pathlib import Path
from unittest import TestCase, main

from azure_vision_classifier import category_from_tags
from fashion_image_analysis import ANALYSIS_VERSION, DIMENSIONS
from import_aloruh_customer import DatasetState, write_outputs

class AzureVisionClassifierTests(TestCase):
    def test_maps_specific_fashion_tag_before_generic_top(self):
        result = category_from_tags([
            {"name": "day dress", "confidence": 0.84},
            {"name": "top", "confidence": 0.59},
        ])
        self.assertEqual("DRESSES", result["category"])
        self.assertEqual("azure_ai_vision_tags", result["category_method"])

    def test_unmapped_tags_are_explicitly_low_confidence(self):
        result = category_from_tags([{"name": "clothing", "confidence": 0.99}])
        self.assertEqual({
            "category": "OTHER",
            "category_confidence": 0.2,
            "category_method": "azure_ai_vision_tags",
        }, result)


class CustomerOutputTests(TestCase):
    def test_writes_multidimensional_analysis_to_catalog_and_image_index(self):
        tags = {
            "product_category": ["DRESSES"], "silhouette_fit": ["FITTED"],
            "design_elements": ["BACKLESS"], "occasion": ["VACATION"],
            "composition": ["FULL_BODY"], "view_action": ["BACK_VIEW"],
            "selling_points": ["BACK"], "scene": ["BEACH"],
            "material_texture": ["SATIN_LIKE"],
            "color_pattern": ["COLOR_BLUE", "PATTERN_SOLID"],
            "visual_language": ["LIFESTYLE"], "styling": ["FULL_LOOK"],
        }
        analysis = {
            "analysis_version": ANALYSIS_VERSION, "analysis_status": "complete",
            "analysis_method": "azure_openai_visual", "tags": tags,
            "confidence": {dimension: 0.9 for dimension in DIMENSIONS},
        }
        rows = [{
            "SKC": "sku-1", "商品ID": "product-1", "图片": "https://example/sku-1.jpg",
            "真实上架时间": "2026-08-01", "店铺名称": "Aloruh",
        }]
        with tempfile.TemporaryDirectory() as temp:
            output_dir = Path(temp)
            write_outputs(rows, DatasetState(set(), {"sku-1": analysis}), output_dir)

            catalog = json.loads((output_dir / "catalog_aloruh_customer.jsonl").read_text(
                encoding="utf-8",
            ))
            image = json.loads((output_dir / "images_aloruh_customer.jsonl").read_text(
                encoding="utf-8",
            ))

        self.assertEqual("DRESSES", catalog["category"])
        self.assertEqual(analysis, catalog["image_analysis"])
        self.assertEqual(analysis, image["analysis"])


if __name__ == "__main__":
    main()
