import unittest

from collect_catalogs import normalize_woocommerce


class WooCommerceCatalogTest(unittest.TestCase):
    def test_normalize_woocommerce_keeps_public_product_evidence(self):
        product = {
            "id": 16032,
            "name": "France Style &#8211; Enchanted Floral Garden Cottage Dress",
            "slug": "enchanted-floral-garden-cottage-dress",
            "permalink": "https://aloruh.com/product/enchanted-floral-garden-cottage-dress/",
            "prices": {
                "price": "3000",
                "regular_price": "4000",
                "sale_price": "3000",
                "currency_code": "USD",
                "currency_minor_unit": 2,
            },
            "on_sale": True,
            "is_in_stock": True,
            "review_count": 0,
            "attributes": [
                {"name": "Size", "terms": [{"name": "S"}, {"name": "M"}]},
                {"name": "Colour", "terms": [{"name": "Blue"}]},
            ],
            "images": [
                {"src": "https://aloruh.com/image-1.jpg"},
                {"src": "https://aloruh.com/image-2.jpg"},
            ],
        }

        row = normalize_woocommerce("aloruh", product, 1)

        self.assertEqual("16032", row["product_id"])
        self.assertEqual("Dresses", row["category"])
        self.assertEqual(30, row["price_usd"])
        self.assertEqual(40, row["was_price_usd"])
        self.assertEqual(0.25, row["discount_rate"])
        self.assertEqual(["S", "M"], row["sizes"])
        self.assertEqual(["Blue"], row["colours"])
        self.assertEqual(2, row["image_count"])
        self.assertEqual("official_woocommerce_store_api", row["source_type"])


if __name__ == "__main__":
    unittest.main()
