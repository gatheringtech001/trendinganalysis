from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CATEGORY_TERMS = {
    "SWIMWEAR": ("bikini", "swimwear", "swimsuit", "bathing suit"),
    "LINGERIE": ("lingerie", "underwear", "bra", "brassiere", "panties"),
    "JUMPSUITS": ("jumpsuit",),
    "PLAYSUITS": ("playsuit", "romper"),
    "SETS": ("two-piece", "pantsuit", "skirt suit", "suit"),
    "DRESSES": ("day dress", "cocktail dress", "evening dress", "gown", "dress"),
    "SKIRTS": ("miniskirt", "skirt"),
    "SHORTS": ("shorts",),
    "JEANS": ("jeans", "denim pants"),
    "TROUSERS": ("trousers", "pants"),
    "OUTERWEAR": ("overcoat", "coat", "jacket", "blazer", "cardigan"),
    "SHOES": ("footwear", "shoe", "boot", "sandal"),
    "ACCESSORIES": ("handbag", "bag", "belt", "hat", "jewelry", "necklace"),
    "TOPS": ("crop top", "blouse", "shirt", "sweater", "t-shirt", "top"),
}


def category_from_tags(tags: list[dict]) -> dict:
    scores = {}
    for category, terms in CATEGORY_TERMS.items():
        scores[category] = max(
            (float(tag["confidence"]) for tag in tags if tag["name"].casefold() in terms),
            default=0,
        )
    category = max(scores, key=scores.get)
    score = scores[category]
    if score == 0:
        return {"category": "OTHER", "category_confidence": 0.2,
                "category_method": "azure_ai_vision_tags"}
    return {"category": category, "category_confidence": round(min(0.9, score * 0.9), 4),
            "category_method": "azure_ai_vision_tags"}


def classify_with_vision(image_url: str, endpoint: str, token: str) -> dict:
    image_request = Request(image_url, headers={"User-Agent": "FashionScope/1.0"})
    with urlopen(image_request, timeout=30) as response:
        image = response.read(2_000_001)
        content_type = response.headers.get_content_type()
    if len(image) > 2_000_000 or not content_type.startswith("image/"):
        raise ValueError("invalid image response for Azure AI Vision")
    query = urlencode({"api-version": "2024-02-01", "features": "tags", "language": "en"})
    request = Request(
        f"{endpoint.rstrip('/')}/computervision/imageanalysis:analyze?{query}",
        data=image,
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )
    with urlopen(request, timeout=60) as response:
        tags = json.load(response)["tagsResult"]["values"]
    return category_from_tags(tags)
