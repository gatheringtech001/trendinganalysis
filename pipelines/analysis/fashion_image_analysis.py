from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


LEGACY_ANALYSIS_VERSION = "fashion-image-v1"
ANALYSIS_VERSION = "fashion-image-v2"
UNKNOWN = "UNKNOWN"
TAXONOMY = {
    "product_category": (
        "DRESSES", "TOPS", "SKIRTS", "TROUSERS", "SHORTS", "SWIMWEAR",
        "OUTERWEAR", "JEANS", "JUMPSUITS", "PLAYSUITS", "SETS", "LINGERIE",
        "ACCESSORIES", "SHOES", "OTHER", UNKNOWN,
    ),
    "silhouette_fit": (
        "BODYCON", "FITTED", "SLIM", "REGULAR", "RELAXED", "OVERSIZED",
        "A_LINE", "STRAIGHT", "FLARED", "DRAPED", "CORSETED", UNKNOWN,
    ),
    "design_elements": (
        "BACKLESS", "CUTOUT", "HALTER", "OFF_SHOULDER", "STRAPLESS",
        "SPAGHETTI_STRAP", "LACE_UP", "SLIT", "RUFFLE", "TIE_DETAIL",
        "RUCHED", "ASYMMETRIC", "SHEER_PANEL", "EMBELLISHED", "PLEATED", UNKNOWN,
    ),
    "occasion": (
        "CASUAL", "GOING_OUT", "PARTY", "DATE_NIGHT", "VACATION", "BEACH",
        "POOL", "WEDDING_GUEST", "FESTIVAL", "COMMUTE", "FORMAL", "HOME", UNKNOWN,
    ),
    "composition": (
        "FULL_BODY", "THREE_QUARTER", "HALF_BODY", "CLOSE_UP", "DETAIL",
        "FLAT_LAY", "PRODUCT_ONLY", UNKNOWN,
    ),
    "view_action": (
        "FRONT_VIEW", "SIDE_VIEW", "BACK_VIEW", "TURNING_BACK", "WALKING",
        "SITTING", "STANDING", "MIRROR_SELFIE", "HAIR_MOVED", "LOOKING_AWAY",
        "INTERACTING_WITH_SCENE", UNKNOWN,
    ),
    "selling_points": (
        "NECKLINE", "SHOULDERS", "BACK", "WAIST", "WAIST_HIP", "LEGS",
        "HEMLINE", "SLEEVES", "FABRIC_TEXTURE", "DRAPE", "PRINT", "FULL_OUTFIT",
        UNKNOWN,
    ),
    "scene": (
        "STUDIO_NEUTRAL", "HOME", "MIRROR", "BEDROOM", "GARDEN", "STREET",
        "BEACH", "POOL", "PARTY", "NIGHT", "ARCHITECTURE", "NATURE", "OTHER",
        UNKNOWN,
    ),
    "material_texture": (
        "KNIT", "LACE", "SATIN_LIKE", "SILK_LIKE", "DENIM", "COTTON_LIKE",
        "CHIFFON", "MESH", "SEQUIN", "LEATHER_LIKE", "RIBBED", "CROCHET",
        "PLEATED", UNKNOWN,
    ),
    "color_pattern": (
        "COLOR_BLACK", "COLOR_WHITE", "COLOR_GREY", "COLOR_BEIGE", "COLOR_BROWN",
        "COLOR_RED", "COLOR_PINK", "COLOR_ORANGE", "COLOR_YELLOW", "COLOR_GREEN",
        "COLOR_BLUE", "COLOR_PURPLE", "COLOR_METALLIC", "COLOR_MULTI",
        "PATTERN_SOLID", "PATTERN_FLORAL", "PATTERN_STRIPE", "PATTERN_CHECK",
        "PATTERN_ANIMAL", "PATTERN_ABSTRACT", "PATTERN_GRAPHIC", UNKNOWN,
    ),
    "visual_language": (
        "ECOMMERCE_CLEAN", "EDITORIAL", "LIFESTYLE", "SOCIAL_UGC", "ROMANTIC",
        "VINTAGE", "Y2K", "MINIMAL", "GLAMOROUS", "SOFT_LIGHT", "NATURAL_LIGHT",
        "DIRECT_FLASH", "WARM_TONE", "COOL_TONE", UNKNOWN,
    ),
    "styling": (
        "SINGLE_ITEM", "FULL_LOOK", "LAYERED", "ACCESSORIES_VISIBLE", "HANDBAG",
        "SHOES_VISIBLE", "JEWELRY", "MATCHING_SET", "SWIM_COVERUP", UNKNOWN,
    ),
    "lighting": (
        "SOFT_DIFFUSED", "NATURAL_DAYLIGHT", "HARD_DIRECT", "DIRECT_FLASH",
        "WARM_AMBIENT", "COOL_AMBIENT", "LOW_KEY", "HIGH_KEY", "MIXED_LIGHT",
        UNKNOWN,
    ),
    "model_state": (
        "NO_MODEL", "STANDING_POSE", "WALKING_MOTION", "SITTING_POSE",
        "LOOKING_CAMERA", "LOOKING_AWAY", "FACE_CROPPED", "MIRROR_SELFIE",
        "INTERACTING", UNKNOWN,
    ),
    "graphic_overlay": (
        "NONE", "TEXT_OVERLAY", "PRICE_PROMOTION", "LOGO_WATERMARK", "COLLAGE",
        "FRAME_BORDER", "STICKER_GRAPHIC", "UI_SCREENSHOT", UNKNOWN,
    ),
}
DIMENSIONS = tuple(TAXONOMY)
LEGACY_DIMENSIONS = DIMENSIONS[:-3]


@dataclass(frozen=True)
class ImageAnalysisRequest:
    key: str
    image_url: str
    title: str = ""
    current_category: str = ""
    position: int = 1


@dataclass(frozen=True)
class AnalysisRunOptions:
    output: Path
    batch_size: int = 8
    workers: int = 4
    progress: Callable[[int, int], None] | None = None


class FashionImageAnalyzer(ABC):
    @abstractmethod
    def analyze(self, batch: list[ImageAnalysisRequest]) -> dict[str, dict]:
        """Return one validated analysis candidate per request key."""


def _validate_labels(dimension: str, values: object) -> list[str]:
    if not isinstance(values, list) or not values:
        raise ValueError(f"{dimension} must be a non-empty list")
    labels = list(dict.fromkeys(str(value).upper() for value in values))
    invalid = set(labels) - set(TAXONOMY[dimension])
    if invalid:
        raise ValueError(f"{dimension} contains invalid labels: {sorted(invalid)}")
    if UNKNOWN in labels and len(labels) != 1:
        labels = [label for label in labels if label != UNKNOWN]
    if dimension == "product_category" and len(labels) != 1:
        raise ValueError("product_category must contain exactly one label")
    return labels


def validate_analysis(value: object) -> dict:
    if not isinstance(value, dict):
        raise ValueError("analysis must be an object")
    version = value.get("analysis_version")
    if version not in {LEGACY_ANALYSIS_VERSION, ANALYSIS_VERSION}:
        raise ValueError("analysis_version is missing or stale")
    status = value.get("analysis_status")
    if status not in {"complete", "partial"}:
        raise ValueError("analysis_status must be complete or partial")
    method = str(value.get("analysis_method") or "")
    if not method:
        raise ValueError("analysis_method is required")
    dimensions = LEGACY_DIMENSIONS if version == LEGACY_ANALYSIS_VERSION else DIMENSIONS
    tags, confidence = value.get("tags"), value.get("confidence")
    if not isinstance(tags, dict) or set(tags) != set(dimensions):
        count = "twelve" if version == LEGACY_ANALYSIS_VERSION else "fifteen"
        raise ValueError(f"tags must contain exactly the {count} dimensions")
    if not isinstance(confidence, dict) or set(confidence) != set(dimensions):
        count = "twelve" if version == LEGACY_ANALYSIS_VERSION else "fifteen"
        raise ValueError(f"confidence must contain exactly the {count} dimensions")
    normalized_tags = {
        dimension: _validate_labels(dimension, tags[dimension])
        for dimension in dimensions
    }
    normalized_confidence = {}
    for dimension in dimensions:
        score = float(confidence[dimension])
        if not 0 <= score <= 1:
            raise ValueError(f"{dimension} confidence must be between 0 and 1")
        normalized_confidence[dimension] = round(score, 4)
    return {
        "analysis_version": version,
        "analysis_status": status,
        "analysis_method": method,
        "tags": normalized_tags,
        "confidence": normalized_confidence,
    }


def _load_cache(paths: tuple[Path, ...]) -> dict[str, dict]:
    results = {}
    for path in paths:
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                analysis = row.get("analysis") or {}
                if analysis.get("analysis_version") != ANALYSIS_VERSION:
                    continue
                key = str(row.get("key") or "")
                if not key:
                    raise ValueError(f"missing analysis key in {path}:{line_number}")
                results[key] = validate_analysis(analysis)
    return results


def _write_results(path: Path, requests: list[ImageAnalysisRequest], results: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    building = path.with_suffix(path.suffix + ".building")
    with building.open("w", encoding="utf-8", newline="\n") as stream:
        for item in requests:
            stream.write(json.dumps(
                {"key": item.key, "analysis": results[item.key]}, ensure_ascii=False,
            ) + "\n")
    os.replace(building, path)


def _validate_batch_result(batch: list[ImageAnalysisRequest], value: object) -> dict[str, dict]:
    if not isinstance(value, dict):
        raise ValueError("analyzer result must be a mapping")
    expected = {item.key for item in batch}
    if set(value) != expected:
        raise ValueError("analyzer result omitted or added request keys")
    return {key: validate_analysis(result) for key, result in value.items()}


def analyze_incremental(
    requests: list[ImageAnalysisRequest], analyzer: FashionImageAnalyzer,
    options: AnalysisRunOptions,
) -> dict[str, dict]:
    output = options.output
    batch_size, workers = options.batch_size, options.workers
    if not 1 <= batch_size <= 32 or not 1 <= workers <= 16:
        raise ValueError("batch_size must be 1..32 and workers must be 1..16")
    keys = [item.key for item in requests]
    if len(keys) != len(set(keys)):
        raise ValueError("analysis request keys must be unique")
    partial = output.with_suffix(output.suffix + ".partial")
    results = _load_cache((output, partial))
    missing = [item for item in requests if item.key not in results]
    batches = [missing[index:index + batch_size] for index in range(0, len(missing), batch_size)]
    output.parent.mkdir(parents=True, exist_ok=True)
    with partial.open("a", encoding="utf-8", newline="\n") as checkpoint:
        executor = ThreadPoolExecutor(max_workers=workers)
        pending, futures = iter(batches), {}

        def submit_next() -> None:
            batch = next(pending, None)
            if batch:
                futures[executor.submit(analyzer.analyze, batch)] = batch

        for _ in range(workers):
            submit_next()
        try:
            while futures:
                future = next(as_completed(futures))
                batch = futures.pop(future)
                try:
                    batch_results = _validate_batch_result(batch, future.result())
                except Exception as error:
                    joined = ", ".join(item.key for item in batch)
                    raise RuntimeError(f"image analysis failed for {joined}") from error
                for key, analysis in batch_results.items():
                    checkpoint.write(json.dumps(
                        {"key": key, "analysis": analysis}, ensure_ascii=False,
                    ) + "\n")
                checkpoint.flush()
                results.update(batch_results)
                if options.progress:
                    options.progress(len(results), len(requests))
                submit_next()
        except BaseException:
            for future in futures:
                future.cancel()
            executor.shutdown(wait=True, cancel_futures=True)
            raise
        else:
            executor.shutdown(wait=True)
    _write_results(output, requests, results)
    partial.unlink(missing_ok=True)
    return {item.key: results[item.key] for item in requests}
