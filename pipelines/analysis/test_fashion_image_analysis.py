import io
import json
import tempfile
import unittest
from http.client import RemoteDisconnected
from pathlib import Path
from unittest.mock import patch

from fashion_image_analysis import (
    ANALYSIS_VERSION,
    AnalysisRunOptions,
    DIMENSIONS,
    FashionImageAnalyzer,
    ImageAnalysisRequest,
    analyze_incremental,
    validate_analysis,
)
from azure_openai_fashion_analyzer import (
    AzureOpenAIFashionAnalyzer,
    AzureOpenAIOptions,
    build_response_schema,
    normalize_image_bytes,
    partial_analysis,
    request_url,
)
from analyze_explorer_images import STORE_FILES, _persist_jsonl


def complete_analysis(category="DRESSES"):
    tags = {
        "product_category": [category],
        "silhouette_fit": ["FITTED"],
        "design_elements": ["BACKLESS"],
        "occasion": ["VACATION"],
        "composition": ["FULL_BODY"],
        "view_action": ["BACK_VIEW", "STANDING"],
        "selling_points": ["BACK", "WAIST"],
        "scene": ["BEACH"],
        "material_texture": ["SATIN_LIKE"],
        "color_pattern": ["COLOR_BLUE", "PATTERN_SOLID"],
        "visual_language": ["LIFESTYLE", "WARM_TONE"],
        "styling": ["FULL_LOOK", "ACCESSORIES_VISIBLE"],
        "lighting": ["NATURAL_DAYLIGHT", "SOFT_DIFFUSED"],
        "model_state": ["STANDING_POSE", "LOOKING_AWAY"],
        "graphic_overlay": ["NONE"],
    }
    return {
        "analysis_version": ANALYSIS_VERSION,
        "analysis_status": "complete",
        "analysis_method": "azure_openai_visual",
        "tags": tags,
        "confidence": {dimension: 0.9 for dimension in DIMENSIONS},
    }


class FakeAnalyzer(FashionImageAnalyzer):
    def __init__(self):
        self.calls = []

    def analyze(self, batch):
        self.calls.append([item.key for item in batch])
        return {item.key: complete_analysis() for item in batch}


class FailingAnalyzer(FashionImageAnalyzer):
    def __init__(self):
        self.calls = []

    def analyze(self, batch):
        self.calls.append([item.key for item in batch])
        if batch[0].key == "bad":
            raise ValueError("bad image")
        return {item.key: complete_analysis() for item in batch}


class AnalysisContractTests(unittest.TestCase):
    def test_aloruh_local_results_write_back_to_customer_dataset(self):
        self.assertEqual("images_aloruh_customer.jsonl", STORE_FILES["aloruh_local"])

    def test_jsonl_reuses_analysis_for_duplicate_image_url(self):
        analysis = complete_analysis("TOPS")
        rows = [
            {"product_id": "one", "position": 1, "source_url": "https://same"},
            {
                "product_id": "two", "position": 1,
                "source_url": "https://same", "analysis": analysis,
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "images.jsonl"
            path.write_text(
                "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8",
            )

            _persist_jsonl(path, {}, {})

            persisted = [json.loads(line) for line in path.read_text(
                encoding="utf-8",
            ).splitlines()]
        self.assertEqual(analysis, persisted[0]["analysis"])
        self.assertEqual(analysis, persisted[1]["analysis"])

    def test_complete_result_requires_all_fifteen_dimensions(self):
        result = validate_analysis(complete_analysis())

        self.assertEqual(set(DIMENSIONS), set(result["tags"]))
        self.assertEqual(set(DIMENSIONS), set(result["confidence"]))

    def test_current_result_rejects_missing_new_dimension(self):
        result = complete_analysis()
        result["tags"].pop("lighting")
        result["confidence"].pop("lighting")

        with self.assertRaisesRegex(ValueError, "fifteen dimensions"):
            validate_analysis(result)

    def test_legacy_twelve_dimension_result_remains_readable(self):
        result = complete_analysis()
        result["analysis_version"] = "fashion-image-v1"
        for dimension in ("lighting", "model_state", "graphic_overlay"):
            result["tags"].pop(dimension)
            result["confidence"].pop(dimension)

        normalized = validate_analysis(result)

        self.assertEqual("fashion-image-v1", normalized["analysis_version"])
        self.assertNotIn("lighting", normalized["tags"])

    def test_unknown_taxonomy_value_is_rejected(self):
        result = complete_analysis()
        result["tags"]["scene"] = ["MOON_BASE"]

        with self.assertRaisesRegex(ValueError, "scene"):
            validate_analysis(result)

    def test_unknown_is_removed_when_specific_label_exists(self):
        result = complete_analysis()
        result["tags"]["material_texture"] = ["UNKNOWN", "SATIN_LIKE"]

        normalized = validate_analysis(result)

        self.assertEqual(["SATIN_LIKE"], normalized["tags"]["material_texture"])

    def test_duplicate_labels_are_deduplicated(self):
        result = complete_analysis()
        result["tags"]["material_texture"] = ["SATIN_LIKE", "SATIN_LIKE"]

        normalized = validate_analysis(result)

        self.assertEqual(["SATIN_LIKE"], normalized["tags"]["material_texture"])

    def test_incremental_runner_reuses_matching_version_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "image_analysis.jsonl"
            output.write_text(
                json.dumps({"key": "cached", "analysis": complete_analysis()}) + "\n",
                encoding="utf-8",
            )
            analyzer = FakeAnalyzer()
            requests = [
                ImageAnalysisRequest("cached", "https://example/cached.jpg"),
                ImageAnalysisRequest("new", "https://example/new.jpg"),
            ]

            results = analyze_incremental(
                requests, analyzer, AnalysisRunOptions(output, batch_size=4, workers=1),
            )

            self.assertEqual([["new"]], analyzer.calls)
            self.assertEqual({"cached", "new"}, set(results))
            written = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual({"cached", "new"}, {row["key"] for row in written})

    def test_failed_batch_does_not_start_queued_batches(self):
        with tempfile.TemporaryDirectory() as temp:
            analyzer = FailingAnalyzer()
            requests = [
                ImageAnalysisRequest("bad", "https://example/bad.jpg"),
                ImageAnalysisRequest("never", "https://example/never.jpg"),
            ]
            options = AnalysisRunOptions(
                Path(temp) / "analysis.jsonl", batch_size=1, workers=1,
            )

            with self.assertRaisesRegex(RuntimeError, "bad"):
                analyze_incremental(requests, analyzer, options)

            self.assertEqual([["bad"]], analyzer.calls)


class AzureAnalyzerContractTests(unittest.TestCase):
    def test_retries_remote_disconnect(self):
        analyzer = AzureOpenAIFashionAnalyzer(
            AzureOpenAIOptions("https://example.openai.azure.com", "key", "terra"),
        )
        request = ImageAnalysisRequest("one", "https://example/one.jpg")
        expected = {"one": complete_analysis()}

        with patch.object(
            analyzer, "_request", side_effect=[RemoteDisconnected(), expected],
        ) as request_call, patch("azure_openai_fashion_analyzer.time.sleep"):
            result = analyzer.analyze([request])

        self.assertEqual(expected, result)
        self.assertEqual(2, request_call.call_count)

    def test_detects_jpeg_from_bytes_instead_of_response_header(self):
        content = b"\xff\xd8\xff" + b"test-payload"

        normalized, mime_type = normalize_image_bytes(content)

        self.assertEqual(content, normalized)
        self.assertEqual("image/jpeg", mime_type)

    def test_reports_response_usage_to_callback(self):
        analysis = complete_analysis()
        output = json.dumps({"items": [{
            "i": 1, "tags": analysis["tags"],
            "confidence": analysis["confidence"],
        }]})
        body = {
            "model": "gpt-5.6-terra",
            "output": [{"content": [{"type": "output_text", "text": output}]}],
            "usage": {
                "input_tokens": 100, "output_tokens": 20, "total_tokens": 120,
            },
        }
        events = []
        analyzer = AzureOpenAIFashionAnalyzer(
            AzureOpenAIOptions("https://example.openai.azure.com", "key", "terra"),
            usage_callback=events.append,
        )
        request = ImageAnalysisRequest("one", "https://example/one.jpg")

        with patch(
            "azure_openai_fashion_analyzer.urlopen",
            return_value=io.BytesIO(json.dumps(body).encode()),
        ):
            analyzer.analyze([request])

        self.assertEqual(1, len(events))
        self.assertEqual("gpt-5.6-terra", events[0]["model"])
        self.assertEqual(1, events[0]["batch_size"])
        self.assertEqual(body["usage"], events[0]["usage"])

    def test_accepts_resource_root_or_complete_deployment_url(self):
        root = AzureOpenAIOptions("https://example.openai.azure.com", "key", "gpt-4.1")
        complete_url = (
            "https://example.cognitiveservices.azure.com/openai/deployments/"
            "gpt-4.1/chat/completions?api-version=2024-05-01-preview"
        )
        complete = AzureOpenAIOptions(complete_url, "key", "ignored")

        expected = "https://example.openai.azure.com/openai/v1/responses"
        self.assertEqual(expected, request_url(root))
        self.assertEqual(
            "https://example.cognitiveservices.azure.com/openai/v1/responses",
            request_url(complete),
        )

    def test_strict_response_schema_contains_every_dimension(self):
        schema = build_response_schema(batch_size=2)
        item = schema["schema"]["properties"]["items"]["items"]

        self.assertTrue(schema["strict"])
        self.assertEqual(set(DIMENSIONS), set(item["properties"]["tags"]["required"]))
        self.assertEqual(set(DIMENSIONS), set(item["properties"]["confidence"]["required"]))
        self.assertEqual(2, schema["schema"]["properties"]["items"]["minItems"])

    def test_vision_fallback_is_explicitly_partial(self):
        result = partial_analysis({
            "category": "LINGERIE", "category_confidence": 0.7,
            "category_method": "azure_ai_vision_tags",
        })

        self.assertEqual("partial", result["analysis_status"])
        self.assertEqual(["LINGERIE"], result["tags"]["product_category"])
        self.assertEqual(["UNKNOWN"], result["tags"]["scene"])
        self.assertEqual(0.0, result["confidence"]["scene"])


if __name__ == "__main__":
    unittest.main()
