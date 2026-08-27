import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analysis_usage import (
    AnalysisUsageRecorder,
    GPT41_STANDARD_PRICING,
    TERRA_STANDARD_PRICING,
    pricing_for_deployment,
)


SAMPLE_EVENT = {
    "model": "gpt-5.6-terra",
    "batch_size": 1,
    "elapsed_seconds": 4.45,
    "usage": {
        "input_tokens": 2002,
        "input_tokens_details": {
            "cache_write_tokens": 1999,
            "cached_tokens": 0,
        },
        "output_tokens": 375,
        "output_tokens_details": {"reasoning_tokens": 124},
        "total_tokens": 2377,
    },
}


class AnalysisUsageRecorderTests(unittest.TestCase):
    def test_selects_pricing_for_supported_deployments(self):
        self.assertIs(TERRA_STANDARD_PRICING, pricing_for_deployment("gpt-5.6-terra"))
        self.assertIs(GPT41_STANDARD_PRICING, pricing_for_deployment("gpt-4.1"))
        with self.assertRaisesRegex(ValueError, "pricing is not configured"):
            pricing_for_deployment("unknown-model")

    def test_records_usage_cost_and_completion_summary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            recorder = AnalysisUsageRecorder(
                root / "usage.jsonl", root / "summary.json",
                total_images=10468, deployment="gpt-5.6-terra",
                pricing=TERRA_STANDARD_PRICING,
            )

            recorder.record(SAMPLE_EVENT)
            recorder.finish("complete", completed_images=10468)

            event = json.loads((root / "usage.jsonl").read_text(encoding="utf-8"))
            summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(1999, event["cache_write_tokens"])
        self.assertEqual(124, event["reasoning_tokens"])
        self.assertAlmostEqual(0.0095035, event["estimated_cost_usd"])
        self.assertEqual("complete", summary["status"])
        self.assertEqual(10468, summary["completed_images"])
        self.assertEqual(2377, summary["total_tokens"])
        self.assertAlmostEqual(0.0095035, summary["estimated_cost_usd"])

    def test_resumes_existing_summary_without_losing_usage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            arguments = {
                "events_path": root / "usage.jsonl",
                "summary_path": root / "summary.json",
                "total_images": 10468,
                "deployment": "gpt-5.6-terra",
                "pricing": TERRA_STANDARD_PRICING,
            }
            AnalysisUsageRecorder(**arguments).record(SAMPLE_EVENT)

            recorder = AnalysisUsageRecorder(**arguments)
            recorder.record(SAMPLE_EVENT)
            summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(2, summary["api_calls"])
        self.assertEqual(4754, summary["total_tokens"])

    def test_retries_summary_replace_when_onedrive_temporarily_denies_access(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            recorder = AnalysisUsageRecorder(
                root / "usage.jsonl", root / "summary.json",
                total_images=10468, deployment="gpt-5.6-terra",
                pricing=TERRA_STANDARD_PRICING,
            )
            original_replace = os.replace
            attempts = 0

            def flaky_replace(source, destination):
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise PermissionError(5, "Access is denied")
                original_replace(source, destination)

            with patch("analysis_usage.os.replace", side_effect=flaky_replace):
                recorder.record(SAMPLE_EVENT)

            summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(2, attempts)
        self.assertEqual(1, summary["api_calls"])


if __name__ == "__main__":
    unittest.main()
