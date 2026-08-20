import unittest

from report_analysis_model import SECTION_IDS, observation_schema, report_schema


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


if __name__ == "__main__":
    unittest.main()
