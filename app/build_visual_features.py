from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PLACEHOLDERS = {("prettylittlething", "PLT15094#white")}

HUE_FAMILIES = (
    (10, "红色"), (25, "橙色"), (40, "黄色"), (85, "绿色"),
    (130, "蓝色"), (160, "紫色"), (180, "粉红"),
)


def _read_image(path: Path) -> np.ndarray | None:
    encoded = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(encoded, cv2.IMREAD_COLOR) if encoded.size else None


def _scaled(image: np.ndarray, maximum: int = 600) -> np.ndarray:
    height, width = image.shape[:2]
    scale = min(maximum / max(height, width), 1)
    if scale == 1:
        return image
    return cv2.resize(image, (round(width * scale), round(height * scale)))


def _border_pixels(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    y_band, x_band = max(round(height * 0.06), 2), max(round(width * 0.06), 2)
    return np.concatenate((
        image[:y_band].reshape(-1, 3), image[-y_band:].reshape(-1, 3),
        image[:, :x_band].reshape(-1, 3), image[:, -x_band:].reshape(-1, 3),
    ))


def _dominant_family(hsv: np.ndarray) -> str:
    pixels = hsv.reshape(-1, 3)
    neutral_share = np.mean((pixels[:, 1] < 45) | (pixels[:, 2] < 35))
    if neutral_share >= 0.55:
        return "中性色"
    colorful = pixels[(pixels[:, 1] >= 45) & (pixels[:, 2] >= 35), 0]
    if not colorful.size:
        return "中性色"
    histogram, _ = np.histogram(colorful, bins=np.arange(0, 181, 5))
    hue = int(np.argmax(histogram) * 5 + 2)
    if hue >= 170:
        return "红色"
    return next(label for upper, label in HUE_FAMILIES if hue < upper)


def _features(image: np.ndarray) -> dict:
    height, width = image.shape[:2]
    sample = _scaled(image)
    rgb = cv2.cvtColor(sample, cv2.COLOR_BGR2RGB)
    hsv = cv2.cvtColor(sample, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(sample, cv2.COLOR_BGR2GRAY)
    border_hsv = cv2.cvtColor(_border_pixels(sample).reshape(-1, 1, 3), cv2.COLOR_BGR2HSV)
    edges = cv2.Canny(gray, 80, 180)
    return {
        "width": width,
        "height": height,
        "brightness": round(float(hsv[:, :, 2].mean() / 255), 4),
        "saturation": round(float(hsv[:, :, 1].mean() / 255), 4),
        "warmth": round(float((rgb[:, :, 0].mean() - rgb[:, :, 2].mean()) / 255), 4),
        "edge_density": round(float(np.mean(edges > 0)), 4),
        "border_brightness": round(float(border_hsv[:, :, 2].mean() / 255), 4),
        "border_saturation": round(float(border_hsv[:, :, 1].mean() / 255), 4),
        "dominant_family": _dominant_family(hsv),
    }


def _row(download: dict) -> dict:
    relative = Path(download["path"])
    store_id = relative.parent.name
    product_id = str(download["product_id"])
    image = _read_image(PROJECT_ROOT / relative)
    base = {
        "store_id": store_id,
        "product_id": product_id,
        "source_url": download["source_url"],
        "content_sha256": download["content_sha256"],
    }
    if image is None:
        return {**base, **dict.fromkeys((
            "width", "height", "brightness", "saturation", "warmth",
            "edge_density", "border_brightness", "border_saturation",
        ), 0), "dominant_family": "未知", "valid": False,
            "exclusion_reason": "image_decode_failed"}
    placeholder = (store_id, product_id) in PLACEHOLDERS
    return {
        **base,
        **_features(image),
        "valid": not placeholder,
        "exclusion_reason": "official_placeholder" if placeholder else "",
    }


def main() -> None:
    downloads = json.loads((DATA_DIR / "downloaded_images.json").read_text(encoding="utf-8"))
    rows = [_row(row) for row in downloads if row.get("status") == "ok"]
    output = DATA_DIR / "visual_features.json"
    output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {store: sum(row["store_id"] == store and row["valid"] for row in rows)
              for store in sorted({row["store_id"] for row in rows})}
    print(json.dumps({"output": str(output), "rows": len(rows), "valid": counts}))


if __name__ == "__main__":
    main()
