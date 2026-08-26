from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from aloruh_shein_parser import is_challenge_url, normalize_browser_export, normalize_card, parse_product_group


BASE_URL = "https://sg.shein.com"
BRAND_URL = f"{BASE_URL}/Brands/Aloruh-sc-0141812390.html"
CARD_SELECTOR = '.product-list[code="goodsList"] .product-card[data-expose-id]'
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT.parent / "2026-08-18" / "data"
DEFAULT_DETAIL_LIMIT = 24
DEFAULT_DELAY_MS = 1_200
NAV_TIMEOUT_MS = 60_000
PAGE_TIMEOUT_MS = 30_000
SG_TZ = timezone(timedelta(hours=8))

CARD_SCRIPT = r"""
cards => cards.map(card => {
  const anchor = card.querySelector('a[data-id][href*="-p-"]');
  const isPlaceholder = url => !url ||
    url.includes('bg-grey-solid-color') ||
    url.includes('images3_ccc/2024/07/25');
  const srcsetUrls = value => (value || '').split(',')
    .map(part => part.trim().split(/\s+/)[0])
    .filter(Boolean);
  const images = Array.from(card.querySelectorAll('img'))
    .filter(img => (img.getAttribute('alt') || '').toLowerCase() !== 'icon')
    .flatMap(img => [
      img.getAttribute('data-src'),
      ...srcsetUrls(img.getAttribute('data-srcset')),
      ...srcsetUrls(img.getAttribute('srcset')),
      img.currentSrc,
      img.getAttribute('src'),
    ])
    .filter(url => !isPlaceholder(url));
  return {
    goods_id: anchor?.getAttribute('data-id') || '',
    store_code: anchor?.getAttribute('data-store_code') || '',
    spu: anchor?.getAttribute('data-spu') || '',
    sku: anchor?.getAttribute('data-sku') || '',
    title: anchor?.getAttribute('data-title') || anchor?.getAttribute('aria-label') || '',
    href: anchor?.getAttribute('href') || '',
    category_id: anchor?.getAttribute('data-cat_id') || '',
    price_sgd: anchor?.getAttribute('data-price') || '',
    price_usd: anchor?.getAttribute('data-us-price') || '',
    discount: anchor?.getAttribute('data-discount') || '',
    text: (card.innerText || '').trim(),
    image_urls: [...new Set(images)],
  };
})
"""


@dataclass(frozen=True)
class CrawlConfig:
    output_dir: Path
    max_pages: int
    detail_limit: int
    delay_ms: int


@dataclass(frozen=True)
class CollectionState:
    retrieved_at: str
    complete: bool
    last_complete_page: int
    failures: list[dict]


def now_iso() -> str:
    return datetime.now(SG_TZ).isoformat(timespec="seconds")


def _has_challenge(page: Page) -> bool:
    if is_challenge_url(page.url):
        return True
    return page.get_by_text("I am human", exact=True).count() > 0


def _raw_cards(page: Page) -> list[dict]:
    return page.locator(CARD_SELECTOR).evaluate_all(CARD_SCRIPT)


def collect_catalog(page: Page, config: CrawlConfig) -> tuple[list[dict], list[dict]]:
    retrieved_at = now_iso()
    catalog: list[dict] = []
    failures: list[dict] = []
    last_complete_page = 0
    complete = False
    page.goto(BRAND_URL, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
    page_number = 1
    while True:
        if _has_challenge(page):
            failures.append({"stage": "catalog", "page": page_number, "reason": "captcha_required", "url": page.url})
            break
        try:
            page.wait_for_selector(CARD_SELECTOR, timeout=PAGE_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            failures.append({"stage": "catalog", "page": page_number, "reason": "product_list_timeout", "url": page.url})
            break
        cards = _raw_cards(page)
        existing = {row["product_id"] for row in catalog}
        for rank, card in enumerate(cards, 1):
            row = normalize_card(card, page_number, rank, retrieved_at)
            if row["product_id"] not in existing:
                catalog.append(row)
                existing.add(row["product_id"])
        last_complete_page = page_number
        _save_catalog_checkpoint(
            config, catalog,
            CollectionState(retrieved_at, False, last_complete_page, failures),
        )
        if config.max_pages and page_number >= config.max_pages:
            break
        next_button = page.get_by_role("button", name="Next page", exact=True)
        if next_button.count() != 1 or next_button.is_disabled():
            complete = True
            break
        old_id = cards[0]["goods_id"] if cards else ""
        next_button.click()
        try:
            page.wait_for_function(
                "oldId => document.querySelector('a[data-id][href*=\"-p-\"]')?.dataset.id !== oldId",
                arg=old_id,
                timeout=PAGE_TIMEOUT_MS,
            )
        except PlaywrightTimeoutError:
            reason = "captcha_required" if _has_challenge(page) else "pagination_timeout"
            failures.append({"stage": "catalog", "page": page_number + 1, "reason": reason, "url": page.url})
            break
        page_number += 1
        page.wait_for_timeout(config.delay_ms)
    _save_catalog_checkpoint(
        config, catalog,
        CollectionState(retrieved_at, complete, last_complete_page, failures),
    )
    return catalog, failures


def _product_group(page: Page) -> dict | None:
    groups = page.locator('script[type="application/ld+json"]').evaluate_all(
        """scripts => scripts.flatMap(script => {
          try {
            const value = JSON.parse(script.textContent || 'null');
            return Array.isArray(value) ? value : [value];
          } catch { return []; }
        }).find(item => item?.['@type'] === 'ProductGroup' && item?.brand?.name === 'Aloruh') || null"""
    )
    return groups


def collect_details(context: BrowserContext, catalog: list[dict], config: CrawlConfig) -> tuple[list[dict], list[dict], list[dict]]:
    if config.detail_limit == 0:
        return [], [], []
    selected = catalog if config.detail_limit < 0 else catalog[: config.detail_limit]
    details: list[dict] = []
    images: list[dict] = []
    failures: list[dict] = []
    page = context.new_page()
    for row in selected:
        try:
            page.goto(row["source_url"], wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
            if _has_challenge(page):
                failures.append({"stage": "detail", "product_id": row["product_id"], "reason": "captcha_required", "url": page.url})
                break
            page.wait_for_function(
                "() => Array.from(document.querySelectorAll('script[type=\"application/ld+json\"]')).some(s => (s.textContent || '').includes('ProductGroup'))",
                timeout=PAGE_TIMEOUT_MS,
            )
            group = _product_group(page)
            if not group:
                raise ValueError("Aloruh ProductGroup JSON-LD not found")
            detail, image_rows = parse_product_group(group, row["source_url"], now_iso())
            details.append(detail)
            images.extend(image_rows)
        except (PlaywrightTimeoutError, ValueError) as exc:
            failures.append({"stage": "detail", "product_id": row["product_id"], "reason": type(exc).__name__, "error": str(exc)[:300], "url": row["source_url"]})
        page.wait_for_timeout(config.delay_ms)
    page.close()
    return details, images, failures


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


def _save_catalog_checkpoint(
    config: CrawlConfig,
    catalog: list[dict],
    state: CollectionState,
) -> None:
    _write_jsonl(config.output_dir / "catalog_aloruh_shein.partial.jsonl", catalog)
    _write_json(config.output_dir / "aloruh_shein_collection_state.json", {
        "retrieved_at": state.retrieved_at,
        "complete": state.complete,
        "last_complete_page": state.last_complete_page,
        "catalog_rows": len(catalog),
        "failures": state.failures,
    })


def save_results(config: CrawlConfig, catalog: list[dict], details: list[dict], images: list[dict], failures: list[dict]) -> dict:
    _write_jsonl(config.output_dir / "catalog_aloruh_shein.jsonl", catalog)
    _write_jsonl(config.output_dir / "details_aloruh_shein.jsonl", details)
    _write_jsonl(config.output_dir / "images_aloruh_shein.jsonl", images)
    _write_json(config.output_dir / "failures_aloruh_shein.json", failures)
    summary = {
        "catalog_rows": len(catalog),
        "detail_rows": len(details),
        "image_rows": len(images),
        "failure_rows": len(failures),
        "detail_coverage": round(len(details) / len(catalog), 4) if catalog else 0,
        "source": BRAND_URL,
        "generated_at": now_iso(),
    }
    _write_json(config.output_dir / "catalog_aloruh_shein_summary.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect public Aloruh catalog and image evidence from SHEIN Singapore")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-pages", type=int, default=0, help="0 means continue until Next page is disabled")
    parser.add_argument("--detail-limit", type=int, default=DEFAULT_DETAIL_LIMIT, help="0 skips detail pages; -1 visits all")
    parser.add_argument("--delay-ms", type=int, default=DEFAULT_DELAY_MS)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--browser-export", type=Path, help="Import a public-data export from the built-in browser")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = CrawlConfig(args.output_dir, args.max_pages, args.detail_limit, args.delay_ms)
    if args.browser_export:
        payload = json.loads(args.browser_export.read_text(encoding="utf-8"))
        summary = save_results(config, *normalize_browser_export(payload))
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=not args.headed)
        context = browser.new_context(locale="en-SG", timezone_id="Asia/Singapore", viewport={"width": 1280, "height": 720})
        context.set_default_timeout(PAGE_TIMEOUT_MS)
        page = context.new_page()
        catalog, failures = collect_catalog(page, config)
        details, images, detail_failures = collect_details(context, catalog, config)
        summary = save_results(config, catalog, details, images, failures + detail_failures)
        browser.close()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
