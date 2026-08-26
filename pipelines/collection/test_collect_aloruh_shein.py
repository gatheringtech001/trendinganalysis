import json
import tempfile
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

from aloruh_shein_parser import (
    is_challenge_url,
    normalize_browser_export,
    normalize_card,
    parse_product_group,
)
from collect_aloruh_shein import (
    CARD_SCRIPT,
    CARD_SELECTOR,
    CollectionState,
    CrawlConfig,
    _save_catalog_checkpoint,
)


RETRIEVED_AT = "2026-08-18T10:00:00+08:00"


class SheinCardTest(unittest.TestCase):
    def test_card_script_prefers_real_lazy_image_over_placeholder(self):
        html = """
        <div class="product-list" code="goodsList">
          <article class="product-card" data-expose-id="card-1">
            <a data-id="510828550" href="/Aloruh-Aqua-Top-p-510828550.html"></a>
            <img alt="Aloruh Aqua Top"
                 src="https://sc.ltwebstatic.com/she_dist/images/bg-grey-solid-color.png"
                 data-src="//img.ltwebstatic.com/main_thumbnail_600x.avif">
          </article>
        </div>
        """
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page()
            page.set_content(html)
            cards = page.locator(CARD_SELECTOR).evaluate_all(CARD_SCRIPT)
            browser.close()

        self.assertEqual(
            ["//img.ltwebstatic.com/main_thumbnail_600x.avif"],
            cards[0]["image_urls"],
        )

    def test_catalog_checkpoint_records_last_complete_page(self):
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            config = CrawlConfig(output_dir, max_pages=0, detail_limit=0, delay_ms=0)
            catalog = [{"product_id": "510828550"}]

            _save_catalog_checkpoint(
                config, catalog,
                CollectionState(RETRIEVED_AT, False, 3, []),
            )

            rows = (output_dir / "catalog_aloruh_shein.partial.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            state = json.loads((output_dir / "aloruh_shein_collection_state.json").read_text(
                encoding="utf-8"
            ))
            self.assertEqual(1, len(rows))
            self.assertEqual(3, state["last_complete_page"])
            self.assertFalse(state["complete"])

    def test_normalize_card_keeps_public_sales_and_images(self):
        card = {
            "goods_id": "510828550",
            "store_code": "4534970445",
            "spu": "z2607211040640213",
            "sku": "sz260528113104394597833",
            "title": "Aloruh Aqua Blue V-Neck Top",
            "href": "/Aloruh-Aqua-Top-p-510828550.html?mallCode=1",
            "category_id": "1738",
            "price_sgd": "7.19",
            "price_usd": "5.63",
            "discount": "10",
            "text": "#2 Bestseller\n100+ sold\nEstimated",
            "image_urls": [
                "//img.ltwebstatic.com/main_thumbnail_600x.avif",
                "https://img.ltwebstatic.com/main_thumbnail_600x.avif",
                "//img.ltwebstatic.com/hover_thumbnail_600x.avif",
            ],
        }

        row = normalize_card(card, page_number=2, page_rank=3, retrieved_at=RETRIEVED_AT)

        self.assertEqual("510828550", row["product_id"])
        self.assertEqual("4534970445", row["store_code"])
        self.assertEqual(123, row["catalog_rank"])
        self.assertEqual(0.1, row["discount_rate"])
        self.assertEqual("100+ sold", row["estimated_sold_label"])
        self.assertTrue(row["sales_is_estimated"])
        self.assertEqual(2, row["bestseller_rank"])
        self.assertEqual(2, row["image_count"])
        self.assertEqual(
            "https://img.ltwebstatic.com/main_thumbnail_600x.avif",
            row["primary_image_url"],
        )
        self.assertEqual(
            "https://sg.shein.com/Aloruh-Aqua-Top-p-510828550.html",
            row["source_url"],
        )

    def test_challenge_url_is_explicit(self):
        self.assertTrue(is_challenge_url("https://sg.shein.com/risk/challenge?captcha_type=909"))
        self.assertFalse(is_challenge_url("https://sg.shein.com/Brands/Aloruh-sc-0141812390.html"))


class SheinProductGroupTest(unittest.TestCase):
    def test_parse_product_group_builds_detail_and_image_rows(self):
        group = {
            "@type": "ProductGroup",
            "name": "Aloruh Baby Pink Dress",
            "brand": {"@type": "Brand", "name": "Aloruh"},
            "productGroupID": "z2511130200870",
            "color": "Baby Pink",
            "image": [
                "https://img.ltwebstatic.com/view1_thumbnail_900x.webp",
                "https://img.ltwebstatic.com/view2_thumbnail_900x.webp",
            ],
            "hasVariant": [
                {
                    "sku": "sku-s",
                    "size": "S",
                    "offers": {
                        "price": "16.49",
                        "priceCurrency": "SGD",
                        "availability": "https://schema.org/InStock",
                    },
                },
                {
                    "sku": "sku-m",
                    "size": "M",
                    "offers": {
                        "price": "26.99",
                        "priceCurrency": "SGD",
                        "availability": "https://schema.org/InStock",
                    },
                },
            ],
        }
        url = "https://sg.shein.com/Aloruh-Baby-Pink-Dress-p-500287144.html"

        detail, images = parse_product_group(group, url, RETRIEVED_AT)

        self.assertEqual("500287144", detail["product_id"])
        self.assertEqual("z2511130200870", detail["product_group_id"])
        self.assertEqual(["S", "M"], detail["sizes"])
        self.assertEqual(16.49, detail["price_min_sgd"])
        self.assertEqual(26.99, detail["price_max_sgd"])
        self.assertTrue(detail["available"])
        self.assertEqual(2, detail["image_count"])
        self.assertEqual([1, 2], [row["position"] for row in images])
        self.assertTrue(all(row["color"] == "Baby Pink" for row in images))
        self.assertTrue(all(row["content_sha256"] is None for row in images))

    def test_normalize_browser_export_uses_same_evidence_schema(self):
        payload = {
            "retrieved_at": RETRIEVED_AT,
            "catalog_pages": [
                {
                    "page_number": 1,
                    "cards": [
                        {
                            "goods_id": "500287144",
                            "store_code": "4534970445",
                            "title": "Aloruh Baby Pink Dress",
                            "href": "/Aloruh-Baby-Pink-Dress-p-500287144.html",
                            "text": "80+ sold\nEstimated",
                            "image_urls": ["//img.ltwebstatic.com/card.avif"],
                        }
                    ],
                }
            ],
            "product_groups": [
                {
                    "source_url": "https://sg.shein.com/Aloruh-Baby-Pink-Dress-p-500287144.html",
                    "group": {
                        "@type": "ProductGroup",
                        "name": "Aloruh Baby Pink Dress",
                        "brand": {"name": "Aloruh"},
                        "color": "Baby Pink",
                        "image": ["https://img.ltwebstatic.com/view1_thumbnail_900x.webp"],
                    },
                }
            ],
            "failures": [],
        }

        catalog, details, images, failures = normalize_browser_export(payload)

        self.assertEqual(1, len(catalog))
        self.assertEqual("80+ sold", catalog[0]["estimated_sold_label"])
        self.assertEqual(1, len(details))
        self.assertEqual(1, len(images))
        self.assertEqual([], failures)


if __name__ == "__main__":
    unittest.main()
