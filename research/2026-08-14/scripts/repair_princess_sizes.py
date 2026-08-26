"""Rebuild normalized Shopify rows after correcting size and colour parsing."""

import gzip
import json
from pathlib import Path

from collect_catalogs import normalize_shopify


BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
STORES = {
    "princess_polly": "https://us.princesspolly.com",
    "motel": "https://us.motelrocks.com",
}


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def rebuild(store: str, base_url: str) -> dict:
    with gzip.open(BASE / "raw" / f"{store}_products.json.gz", "rt", encoding="utf-8") as handle:
        products = json.load(handle)
    rows = [normalize_shopify(store, base_url, product, rank) for rank, product in enumerate(products, 1)]
    write_jsonl(DATA / f"catalog_{store}.jsonl", rows)
    sample_path = DATA / f"sample_{store}.json"
    old_sample = json.loads(sample_path.read_text(encoding="utf-8"))
    by_id = {row["product_id"]: row for row in rows}
    rebuilt = []
    for old in old_sample:
        row = dict(by_id[old["product_id"]])
        row["sample_bucket"] = old["sample_bucket"]
        row["bucket_rank"] = old["bucket_rank"]
        rebuilt.append(row)
    sample_path.write_text(json.dumps(rebuilt, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "catalog_rows": len(rows),
        "sample_rows": len(rebuilt),
        "rows_with_sizes": sum(bool(row["sizes"]) for row in rows),
        "rows_with_colours": sum(bool(row["colours"]) for row in rows),
    }


def main() -> None:
    print(json.dumps({store: rebuild(store, base) for store, base in STORES.items()}))


if __name__ == "__main__":
    main()
