from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path

from aloruh_customer_source import read_source
from analysis_usage import AnalysisUsageRecorder, TERRA_STANDARD_PRICING
from azure_openai_fashion_analyzer import (
    AzureOpenAIFashionAnalyzer,
    AzureOpenAIOptions,
)
from azure_vision_classifier import classify_with_vision
from fashion_image_analysis import (
    AnalysisRunOptions,
    ImageAnalysisRequest,
    analyze_incremental,
)


MANUAL_OVERRIDES = {
    "sz25052308383593303": {
        "category": "DRESSES", "category_confidence": 1.0,
        "category_method": "manual_visual_review",
    },
}
URL_PATTERN = re.compile(r"https?://[^\s,;，；|]+", re.IGNORECASE)


@dataclass(frozen=True)
class DatasetState:
    local_skcs: set[str]
    analyses: dict[str, dict]


def image_url(row: dict[str, str]) -> str:
    matches = URL_PATTERN.findall(row["图片"])
    if len(matches) != 1:
        raise ValueError(f"SKC {row['SKC']} must have exactly one image URL")
    return matches[0].replace("http://", "https://", 1)


def analysis_requests(rows: list[dict[str, str]]) -> list[ImageAnalysisRequest]:
    return [
        ImageAnalysisRequest(
            key=row["SKC"].strip(), image_url=image_url(row),
            title=f"Aloruh {row['SKC'].strip()}",
        )
        for row in rows
    ]


def category_fields(skc: str, analysis: dict) -> dict:
    override = MANUAL_OVERRIDES.get(skc)
    if override:
        return override
    return {
        "category": analysis["tags"]["product_category"][0],
        "category_confidence": analysis["confidence"]["product_category"],
        "category_method": analysis["analysis_method"],
    }


def write_outputs(rows: list[dict[str, str]], state: DatasetState,
                  output_dir: Path) -> None:
    if len(state.analyses) != len(rows):
        raise ValueError(f"analysis coverage {len(state.analyses)}/{len(rows)}")
    generated_at = datetime.now(timezone.utc).isoformat()
    catalog, images = [], []
    for rank, row in enumerate(rows, 20):
        skc, url = row["SKC"].strip(), image_url(row)
        analysis = state.analyses[skc]
        classification = category_fields(skc, analysis)
        catalog.append({
            "store_id": "aloruh", "market": "US", "product_id": skc,
            "handle": f"customer-{skc.lower()}", "title": f"Aloruh {skc}",
            "brand": "Aloruh", "category": classification["category"],
            "category_method": classification["category_method"],
            "category_confidence": classification["category_confidence"],
            "price_usd": None, "was_price_usd": None, "discount_rate": 0,
            "on_sale": False, "available": True, "sizes": [], "colours": [],
            "primary_image_url": url, "image_count": 1, "image_urls": [url],
            "source_type": "customer_dataset", "source_url": url,
            "catalog_rank": rank, "local_copy_supplied": skc in state.local_skcs,
            "listed_at": row["真实上架时间"], "retrieved_at": generated_at,
            "image_analysis": analysis,
            "customer_metrics": {key: value for key, value in row.items()
                                 if key not in {"图片", "店铺名称", "SKC"}},
        })
        images.append({
            "store_id": "aloruh", "product_id": skc, "position": 1,
            "source_url": url, "url_sha256": hashlib.sha256(url.encode()).hexdigest(),
            "content_sha256": "", "sample_product": skc in state.local_skcs,
            "analysis": analysis,
        })
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, values in (("catalog_aloruh_customer.jsonl", catalog),
                         ("images_aloruh_customer.jsonl", images)):
        target = output_dir / name
        building = target.with_suffix(target.suffix + ".building")
        with building.open("w", encoding="utf-8", newline="\n") as stream:
            for value in values:
                stream.write(json.dumps(value, ensure_ascii=False) + "\n")
        os.replace(building, target)


def build_analyzer(args, usage_callback=None) -> AzureOpenAIFashionAnalyzer:
    options = AzureOpenAIOptions(
        endpoint=args.endpoint, credential=args.credential,
        deployment=args.deployment, auth_type=args.auth_type,
    )
    fallback = None
    if args.vision_endpoint:
        if not args.vision_token:
            raise SystemExit("--vision-token is required when --vision-endpoint is set")

        def fallback(request: ImageAnalysisRequest) -> dict:
            return classify_with_vision(
                request.image_url, args.vision_endpoint, args.vision_token,
            )
    return AzureOpenAIFashionAnalyzer(
        options, category_fallback=fallback, usage_callback=usage_callback,
    )


def print_progress(completed: int, total: int) -> None:
    print(f"analyzed={completed}/{total}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import and analyze customer Aloruh images",
    )
    parser.add_argument("source_zip", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("AZURE_OPENAI_ENDPOINT")
        or os.environ.get("ALORUH_AOAI_ENDPOINT", ""),
    )
    parser.add_argument(
        "--credential",
        default=os.environ.get("AZURE_OPENAI_KEY")
        or os.environ.get("AZURE_OPENAI_API_KEY")
        or os.environ.get("ALORUH_AOAI_TOKEN", ""),
    )
    has_api_key = os.environ.get("AZURE_OPENAI_KEY") or os.environ.get("AZURE_OPENAI_API_KEY")
    default_auth = "api_key" if has_api_key else "bearer"
    parser.add_argument("--auth-type", choices=("api_key", "bearer"), default=default_auth)
    parser.add_argument("--vision-endpoint", default=os.environ.get("ALORUH_VISION_ENDPOINT", ""))
    parser.add_argument("--vision-token", default=os.environ.get("ALORUH_AOAI_TOKEN", ""))
    parser.add_argument(
        "--deployment", default=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1"),
    )
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if not args.endpoint or not args.credential:
        raise SystemExit("Azure OpenAI endpoint and credential are required")
    if not 1 <= args.batch_size <= 32 or not 1 <= args.workers <= 16:
        raise SystemExit("batch size must be 1..32 and workers must be 1..16")
    rows, local_skcs = read_source(args.source_zip)
    analysis_output = args.output_dir / "image_analysis_aloruh_customer.jsonl"
    if args.deployment != "gpt-5.6-terra":
        raise SystemExit("usage pricing is configured only for gpt-5.6-terra")
    usage = AnalysisUsageRecorder(
        args.output_dir / "image_analysis_aloruh_customer.usage.jsonl",
        args.output_dir / "image_analysis_aloruh_customer.usage-summary.json",
        total_images=len(rows), deployment=args.deployment,
        pricing=TERRA_STANDARD_PRICING,
    )
    try:
        analyses = analyze_incremental(
            analysis_requests(rows), build_analyzer(args, usage.record),
            AnalysisRunOptions(
                analysis_output, batch_size=args.batch_size,
                workers=args.workers, progress=print_progress,
            ),
        )
    except BaseException:
        partial_path = analysis_output.with_suffix(analysis_output.suffix + ".partial")
        completed = (
            sum(1 for _ in partial_path.open(encoding="utf-8"))
            if partial_path.exists() else 0
        )
        usage.finish("failed", completed_images=completed)
        raise
    usage.finish("complete", completed_images=len(analyses))
    write_outputs(rows, DatasetState(local_skcs, analyses), args.output_dir)
    partial = sum(value["analysis_status"] == "partial" for value in analyses.values())
    print(
        f"imported={len(rows)} analyzed={len(analyses)} partial={partial} "
        f"local_copies={len(local_skcs)}"
    )


if __name__ == "__main__":
    main()
