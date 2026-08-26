import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from analysis_usage import SOL_STANDARD_PRICING
from analyze_dimension_selection import (
    _read_filters, select_images, select_images_by_keys,
)
from detailed_visual_analysis import build_detailed_schema
from high_resolution_images import high_resolution_candidates, inspect_image


class HighResolutionImageTests(unittest.TestCase):
    def test_shein_thumbnail_url_is_upgraded_before_original(self):
        source = "https://img.ltwebstatic.com/a/b/item_thumbnail_405x552.jpg"

        candidates = high_resolution_candidates("aloruh_shein", source)

        self.assertEqual("https://img.ltwebstatic.com/a/b/item.jpg", candidates[0])
        self.assertEqual(source, candidates[1])

    def test_image_bytes_are_verified_and_measured(self):
        buffer = io.BytesIO()
        Image.new("RGB", (1200, 1600), "red").save(buffer, format="JPEG")

        width, height, mime, suffix = inspect_image(buffer.getvalue())

        self.assertEqual((1200, 1600), (width, height))
        self.assertEqual(("image/jpeg", ".jpg"), (mime, suffix))

    @patch("high_resolution_images.socket.getaddrinfo")
    def test_private_image_host_is_rejected(self, resolve):
        resolve.return_value = [(None, None, None, None, ("127.0.0.1", 0))]
        from high_resolution_images import _validate_public_host

        with self.assertRaisesRegex(ValueError, "public"):
            _validate_public_host("https://example.test/image.jpg")


class SelectionTests(unittest.TestCase):
    def test_fixed_filters_are_validated(self):
        self.assertEqual({"product_category": "TOPS"}, _read_filters('{"product_category":"TOPS"}'))
        with self.assertRaisesRegex(ValueError, "unknown dimension"):
            _read_filters('{"made_up":"TOPS"}')

    def test_selection_is_balanced_by_store_and_matches_all_filters(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "test.db"
            connection = sqlite3.connect(db)
            connection.executescript("""
                CREATE TABLE images (store_id TEXT, product_id TEXT, position INTEGER, source_url TEXT);
                CREATE TABLE products (store_id TEXT, product_id TEXT, title TEXT, category TEXT, catalog_rank INTEGER);
                CREATE TABLE image_analysis (store_id TEXT, product_id TEXT, position INTEGER, tags_json TEXT);
            """)
            for store in ("one", "two"):
                for index, category in enumerate(("TOPS", "SKIRTS"), 1):
                    product = f"{store}-{index}"
                    connection.execute("INSERT INTO images VALUES (?,?,?,?)", (store, product, 1, f"https://{store}/{index}.jpg"))
                    connection.execute("INSERT INTO products VALUES (?,?,?,?,?)", (store, product, product, category, index))
                    tags = {"product_category": [category], "occasion": ["CASUAL"]}
                    connection.execute("INSERT INTO image_analysis VALUES (?,?,?,?)", (store, product, 1, json.dumps(tags)))
            connection.commit()
            connection.close()

            rows = select_images(db, ["one", "two"], {"product_category": "TOPS", "occasion": "CASUAL"}, 2, 4)

        self.assertEqual(["one", "two"], [row["store_id"] for row in rows])

    def test_manual_selection_preserves_order_and_revalidates_filters(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "test.db"
            connection = sqlite3.connect(db)
            connection.executescript("""
                CREATE TABLE images (store_id TEXT, product_id TEXT, position INTEGER, source_url TEXT);
                CREATE TABLE products (store_id TEXT, product_id TEXT, title TEXT, category TEXT, catalog_rank INTEGER);
                CREATE TABLE image_analysis (store_id TEXT, product_id TEXT, position INTEGER, tags_json TEXT);
            """)
            for index, category in enumerate(("TOPS", "SKIRTS"), 1):
                product = f"motel-{index}"
                connection.execute(
                    "INSERT INTO images VALUES (?,?,?,?)",
                    ("motel", product, 1, f"https://motel/{index}.jpg"),
                )
                connection.execute(
                    "INSERT INTO products VALUES (?,?,?,?,?)",
                    ("motel", product, product, category, index),
                )
                connection.execute(
                    "INSERT INTO image_analysis VALUES (?,?,?,?)",
                    ("motel", product, 1, json.dumps({"product_category": [category]})),
                )
            connection.commit()
            connection.close()

            selected = [{
                "store_id": "motel", "product_id": "motel-1", "position": 1,
            }]
            rows = select_images_by_keys(
                db, ["motel"], {"product_category": "TOPS"}, selected,
            )
            self.assertEqual("motel-1", rows[0]["product_id"])
            with self.assertRaisesRegex(ValueError, "does not match"):
                select_images_by_keys(
                    db, ["motel"], {"product_category": "TOPS"}, [{
                        "store_id": "motel", "product_id": "motel-2", "position": 1,
                    }],
                )


class DetailedSchemaTests(unittest.TestCase):
    def test_schema_requires_every_image_and_store(self):
        schema = build_detailed_schema(3, ["one", "two"])["schema"]

        self.assertEqual(3, schema["properties"]["images"]["minItems"])
        self.assertEqual(2, schema["properties"]["store_summaries"]["minItems"])

    def test_sol_pricing_uses_official_standard_short_context_rates(self):
        self.assertEqual(5.0, SOL_STANDARD_PRICING.input_per_million)
        self.assertEqual(30.0, SOL_STANDARD_PRICING.output_per_million)


if __name__ == "__main__":
    unittest.main()
