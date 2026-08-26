from __future__ import annotations

import base64
import io
import json
import time
from dataclasses import dataclass
from http.client import RemoteDisconnected
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from fashion_image_analysis import (
    ANALYSIS_VERSION,
    DIMENSIONS,
    TAXONOMY,
    UNKNOWN,
    FashionImageAnalyzer,
    ImageAnalysisRequest,
    validate_analysis,
)


MAX_IMAGE_BYTES = 4_000_000
RETRY_CODES = {429, 500, 502, 503, 504}
SUPPORTED_SIGNATURES = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


@dataclass(frozen=True)
class AzureOpenAIOptions:
    endpoint: str
    credential: str
    deployment: str
    auth_type: str = "api_key"

    def __post_init__(self):
        if not self.endpoint or not self.credential or not self.deployment:
            raise ValueError("Azure OpenAI endpoint, credential and deployment are required")
        if self.auth_type not in {"api_key", "bearer"}:
            raise ValueError("auth_type must be api_key or bearer")


def normalize_image_bytes(content: bytes) -> tuple[bytes, str]:
    for signature, mime_type in SUPPORTED_SIGNATURES:
        if content.startswith(signature):
            return content, mime_type
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return content, "image/webp"
    from PIL import Image
    with Image.open(io.BytesIO(content)) as image:
        converted = io.BytesIO()
        image.convert("RGB").save(converted, format="JPEG", quality=90)
    return converted.getvalue(), "image/jpeg"


def image_data_url(image_url: str) -> str:
    request = Request(image_url, headers={"User-Agent": "FashionScope/1.0"})
    with urlopen(request, timeout=30) as response:
        content = response.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise ValueError("invalid image response for fashion analysis")
    content, content_type = normalize_image_bytes(content)
    if len(content) > MAX_IMAGE_BYTES:
        raise ValueError("normalized image is too large for fashion analysis")
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


def validated_image_url(image_url: str) -> str:
    parts = urlsplit(image_url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("fashion image URL must be an absolute HTTP URL")
    return image_url


def _array_schema(dimension: str) -> dict:
    maximum = 1 if dimension == "product_category" else 5
    return {
        "type": "array",
        "items": {"type": "string", "enum": list(TAXONOMY[dimension])},
        "minItems": 1,
        "maxItems": maximum,
    }


def build_response_schema(batch_size: int) -> dict:
    tags = {dimension: _array_schema(dimension) for dimension in DIMENSIONS}
    confidence = {
        dimension: {"type": "number", "minimum": 0, "maximum": 1}
        for dimension in DIMENSIONS
    }
    item = {
        "type": "object",
        "properties": {
            "i": {"type": "integer", "minimum": 1, "maximum": batch_size},
            "tags": {
                "type": "object", "properties": tags,
                "required": list(DIMENSIONS), "additionalProperties": False,
            },
            "confidence": {
                "type": "object", "properties": confidence,
                "required": list(DIMENSIONS), "additionalProperties": False,
            },
        },
        "required": ["i", "tags", "confidence"],
        "additionalProperties": False,
    }
    return {
        "type": "json_schema",
        "name": "fashion_image_analysis",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {"items": {
                "type": "array", "items": item,
                "minItems": batch_size, "maxItems": batch_size,
            }},
            "required": ["items"],
            "additionalProperties": False,
        },
    }


def request_url(options: AzureOpenAIOptions) -> str:
    parts = urlsplit(options.endpoint)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("Azure OpenAI endpoint must be an absolute HTTP URL")
    return urlunsplit((parts.scheme, parts.netloc, "/openai/v1/responses", "", ""))


def partial_analysis(category_result: dict) -> dict:
    category = str(category_result.get("category") or "").upper()
    if category not in TAXONOMY["product_category"]:
        raise ValueError(f"invalid fallback category: {category}")
    category_confidence = float(category_result.get("category_confidence") or 0)
    tags = {dimension: [UNKNOWN] for dimension in DIMENSIONS}
    confidence = {dimension: 0.0 for dimension in DIMENSIONS}
    tags["product_category"] = [category]
    confidence["product_category"] = category_confidence
    return validate_analysis({
        "analysis_version": ANALYSIS_VERSION,
        "analysis_status": "partial",
        "analysis_method": category_result.get("category_method") or "category_fallback",
        "tags": tags,
        "confidence": confidence,
    })


def _taxonomy_prompt() -> str:
    lines = [
        f"{dimension}: {', '.join(values)}"
        for dimension, values in TAXONOMY.items()
    ]
    return (
        "Analyze every numbered fashion image using exactly the controlled codes below. "
        "Use visible evidence and the supplied title/category only. Select UNKNOWN when a "
        "dimension is not observable, and never combine UNKNOWN with another code. "
        "Do not infer ethnicity, health, attractiveness or "
        "other sensitive traits. product_category must have exactly one value. Other "
        "dimensions may have up to five values. Focus on the primary item sold; accessories "
        "belong in styling unless they are the primary product. Return every image once.\n"
        + "\n".join(lines)
    )


class AzureOpenAIFashionAnalyzer(FashionImageAnalyzer):
    def __init__(
        self, options: AzureOpenAIOptions,
        image_loader: Callable[[str], str] = validated_image_url,
        category_fallback: Callable[[ImageAnalysisRequest], dict] | None = None,
        usage_callback: Callable[[dict], None] | None = None,
    ):
        self.options = options
        self.image_loader = image_loader
        self.category_fallback = category_fallback
        self.usage_callback = usage_callback

    def analyze(self, batch: list[ImageAnalysisRequest]) -> dict[str, dict]:
        if not batch:
            return {}
        return self._analyze_resilient(batch)

    def _analyze_resilient(self, batch: list[ImageAnalysisRequest]) -> dict[str, dict]:
        for attempt in range(4):
            try:
                return self._request(batch)
            except HTTPError as error:
                body = self._error_body(error)
                if error.code == 400 and body.get("error", {}).get("code") == "content_policy_violation":
                    return self._handle_policy_block(batch)
                if error.code not in RETRY_CODES or attempt == 3:
                    raise
                delay = max(2 ** attempt, float(error.headers.get("Retry-After", 0)))
            except (RemoteDisconnected, TimeoutError, URLError):
                if attempt == 3:
                    raise
                delay = 2 ** attempt
            time.sleep(min(delay, 30))
        raise RuntimeError("Azure OpenAI retry loop exhausted")

    def _handle_policy_block(self, batch: list[ImageAnalysisRequest]) -> dict[str, dict]:
        if len(batch) > 1:
            middle = len(batch) // 2
            return {
                **self._analyze_resilient(batch[:middle]),
                **self._analyze_resilient(batch[middle:]),
            }
        if not self.category_fallback:
            raise RuntimeError(f"content policy blocked image analysis for {batch[0].key}")
        return {batch[0].key: partial_analysis(self.category_fallback(batch[0]))}

    @staticmethod
    def _error_body(error: HTTPError) -> dict:
        try:
            return json.loads(error.read().decode("utf-8", "replace"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _headers(self) -> dict[str, str]:
        auth = (
            {"api-key": self.options.credential}
            if self.options.auth_type == "api_key"
            else {"Authorization": f"Bearer {self.options.credential}"}
        )
        return {**auth, "Content-Type": "application/json"}

    def _request(self, batch: list[ImageAnalysisRequest]) -> dict[str, dict]:
        content = [{"type": "input_text", "text": _taxonomy_prompt()}]
        for index, item in enumerate(batch, 1):
            context = (
                f"IMAGE {index}; key={item.key}; title={item.title or 'unknown'}; "
                f"current_category={item.current_category or 'unknown'}; position={item.position}"
            )
            content.extend([
                {"type": "input_text", "text": context},
                {"type": "input_image", "image_url": self.image_loader(item.image_url),
                 "detail": "low"},
            ])
        payload = {
            "model": self.options.deployment,
            "input": [{"role": "user", "content": content}],
            "text": {"format": build_response_schema(len(batch))},
            "max_output_tokens": max(2000, len(batch) * 1200),
            "store": False,
        }
        request = Request(
            request_url(self.options), data=json.dumps(payload).encode(),
            method="POST", headers=self._headers(),
        )
        started = time.perf_counter()
        with urlopen(request, timeout=120) as response:
            body = json.load(response)
        if self.usage_callback:
            self.usage_callback({
                "model": body.get("model") or self.options.deployment,
                "batch_size": len(batch),
                "elapsed_seconds": time.perf_counter() - started,
                "usage": body.get("usage"),
            })
        items = json.loads(self._output_text(body))["items"]
        return self._map_results(batch, items)

    @staticmethod
    def _output_text(body: dict) -> str:
        for item in body.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    return content["text"]
        raise ValueError(
            f"Azure OpenAI returned no output text; status={body.get('status', 'unknown')}"
        )

    @staticmethod
    def _map_results(batch: list[ImageAnalysisRequest], items: list[dict]) -> dict[str, dict]:
        expected = set(range(1, len(batch) + 1))
        if {item.get("i") for item in items} != expected or len(items) != len(batch):
            raise ValueError("model response omitted or duplicated an image index")
        results = {}
        for item in items:
            analysis = validate_analysis({
                "analysis_version": ANALYSIS_VERSION,
                "analysis_status": "complete",
                "analysis_method": "azure_openai_visual",
                "tags": item.get("tags"),
                "confidence": item.get("confidence"),
            })
            results[batch[item["i"] - 1].key] = analysis
        return results
