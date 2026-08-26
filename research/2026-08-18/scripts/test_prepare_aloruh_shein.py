import json
import tempfile
import unittest
from pathlib import Path

from prepare_aloruh_shein_for_explorer import prepare


class PrepareAloruhSheinTest(unittest.TestCase):
    def test_merges_deep_details_and_preserves_sales_proxy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / "source", root / "output"
            source.mkdir()
            catalog = [{
                "product_id": "10", "title": "Aloruh Dress", "category_id": "12480",
                "price_sgd": 20, "price_usd": 15.6, "discount_rate": 0,
                "estimated_sold_label": "100+ sold", "sales_is_estimated": True,
                "bestseller_rank": 2, "catalog_rank": 1,
                "image_urls": ["https://example.com/list.jpg"],
                "source_type": "official_shein_brand_page",
                "source_url": "https://sg.shein.com/item-p-10.html",
                "retrieved_at": "2026-08-18T00:00:00+08:00",
            }]
            details = [{
                "product_id": "10", "color": "Blue", "sizes": ["S", "M"],
                "available": True, "image_urls": ["https://example.com/900.jpg"],
                "source_type": "official_shein_product_page_jsonld",
            }]
            images = [{
                "store_id": "aloruh", "product_id": "10", "position": 1,
                "source_url": "https://example.com/900.jpg", "url_sha256": "hash",
            }]
            self.write_jsonl(source / "catalog_aloruh_shein.jsonl", catalog)
            self.write_jsonl(source / "details_aloruh_shein.jsonl", details)
            self.write_jsonl(source / "images_aloruh_shein.jsonl", images)
            (source / "aloruh_shein_browser_export.json").write_text(json.dumps({
                "catalog_pages": [{"cards": [{
                    "goods_id": "10", "text": "-25%\nS$15.00\n100+ sold\nEstimated",
                }]}]
            }), encoding="utf-8")

            summary = prepare(source, output)
            product = json.loads((output / "catalog_aloruh_shein.jsonl").read_text())
            image = json.loads((output / "images_aloruh_shein.jsonl").read_text())
            self.assertEqual(1, summary["products"])
            self.assertEqual("SG", product["market"])
            self.assertEqual("shein_sg", product["channel"])
            self.assertEqual("Maxi Dresses", product["category"])
            self.assertEqual(11.7, product["price_usd"])
            self.assertEqual("https://example.com/900.jpg", product["primary_image_url"])
            self.assertEqual("100+ sold", product["estimated_sold_label"])
            self.assertTrue(product["sales_is_estimated"])
            self.assertFalse(product["top_seller"])
            self.assertTrue(image["sample_product"])

    def test_partial_refresh_dedupes_products_and_image_variants(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / "source", root / "output"
            source.mkdir()
            catalog = [
                self.catalog_row("10", "https://example.com/old.jpg"),
                self.catalog_row("30", "https://example.com/preserved.jpg"),
            ]
            self.write_jsonl(source / "catalog_aloruh_shein.jsonl", catalog)
            self.write_jsonl(source / "details_aloruh_shein.jsonl", [])
            self.write_jsonl(source / "images_aloruh_shein.jsonl", [])
            (source / "aloruh_shein_browser_export.json").write_text(json.dumps({
                "retrieved_at": "2026-08-18T00:00:00Z", "catalog_pages": [],
            }), encoding="utf-8")
            (source / "aloruh_shein_browser_export.recollect.partial.json").write_text(
                json.dumps({
                    "retrieved_at": "2026-08-18T12:00:00Z",
                    "catalog_pages": [
                        {"page_number": 1, "cards": [
                            self.refresh_card("10"), self.refresh_card("20"),
                        ]},
                        {"page_number": 2, "cards": [self.refresh_card("10")]},
                    ],
                    "failures": [{"stage": "catalog", "page": 3, "reason": "risk_crawler_block"}],
                    "collection_state": {"complete": False, "last_complete_page": 2},
                }), encoding="utf-8",
            )

            summary = prepare(source, output)
            products = [json.loads(line) for line in (
                output / "catalog_aloruh_shein.jsonl"
            ).read_text().splitlines()]
            by_id = {row["product_id"]: row for row in products}
            images = [json.loads(line) for line in (
                output / "images_aloruh_shein.jsonl"
            ).read_text().splitlines()]

            self.assertEqual({"10", "20", "30"}, set(by_id))
            self.assertEqual(3, summary["refresh_raw_cards"])
            self.assertEqual(2, summary["refresh_unique_products"])
            self.assertEqual(1, summary["refresh_duplicate_cards"])
            self.assertEqual(1, summary["refresh_updated_products"])
            self.assertEqual(1, summary["refresh_added_products"])
            self.assertFalse(summary["refresh_complete"])
            self.assertEqual(2, summary["refresh_last_complete_page"])
            self.assertEqual(
                "https://img.ltwebstatic.com/a/hash_thumbnail_600x.avif",
                by_id["10"]["primary_image_url"],
            )
            self.assertEqual(1, by_id["10"]["image_count"])
            self.assertEqual(1, len([row for row in images if row["product_id"] == "10"]))
            self.assertEqual(0, by_id["20"]["image_count"])
            self.assertEqual(2, len(images))
            self.assertEqual(1, summary["image_duplicate_rows_removed"])
            self.assertEqual(len(images), len({row["source_url"] for row in images}))
            self.assertEqual("https://example.com/preserved.jpg", by_id["30"]["primary_image_url"])

    @staticmethod
    def catalog_row(product_id, image_url):
        return {
            "product_id": product_id, "title": f"Old {product_id}",
            "category_id": "12480", "price_sgd": 20, "price_usd": 15,
            "discount_rate": 0, "image_urls": [image_url], "catalog_rank": 1,
            "source_type": "official_shein_brand_page",
            "source_url": f"https://sg.shein.com/item-p-{product_id}.html",
            "retrieved_at": "2026-08-18T00:00:00Z",
        }

    @staticmethod
    def refresh_card(product_id):
        return {
            "goods_id": product_id, "title": f"New {product_id}",
            "category_id": "12480", "price_sgd": "18", "price_usd": "14",
            "discount": "10", "href": f"/item-p-{product_id}.html",
            "text": "-10%\nS$18.00\nEstimated",
            "image_urls": [
                "//img.ltwebstatic.com/a/hash_thumbnail_405x552.jpg",
                "https://img.ltwebstatic.com/a/hash_thumbnail_600x.avif",
            ],
        }

    @staticmethod
    def write_jsonl(path, rows):
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
