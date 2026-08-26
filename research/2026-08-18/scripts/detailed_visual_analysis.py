from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from http.client import RemoteDisconnected
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from azure_openai_fashion_analyzer import AzureOpenAIOptions, request_url
from high_resolution_images import DownloadedImage


RETRY_CODES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class DetailedVisualItem:
    image: DownloadedImage
    title: str
    category: str


def _string_array(max_items: int) -> dict:
    return {
        "type": "array", "items": {"type": "string"},
        "minItems": 1, "maxItems": max_items,
    }


def build_detailed_schema(image_count: int, store_ids: list[str]) -> dict:
    evidence = {
        "type": "object",
        "properties": {"claim": {"type": "string"}, "visible_cue": {"type": "string"}},
        "required": ["claim", "visible_cue"], "additionalProperties": False,
    }
    observable_properties = {
        name: {"type": "string"}
        for name in ("scene", "framing", "pose_action", "lighting", "color_palette", "styling", "garment_details")
    }
    image_item = {
        "type": "object",
        "properties": {
            "i": {"type": "integer", "minimum": 1, "maximum": image_count},
            "observable": {
                "type": "object", "properties": observable_properties,
                "required": list(observable_properties), "additionalProperties": False,
            },
            "visual_intent": {"type": "string"},
            "strengths": _string_array(5),
            "weaknesses": _string_array(5),
            "recommended_changes": _string_array(5),
            "evidence": {"type": "array", "items": evidence, "minItems": 2, "maxItems": 6},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": [
            "i", "observable", "visual_intent", "strengths", "weaknesses",
            "recommended_changes", "evidence", "confidence",
        ],
        "additionalProperties": False,
    }
    store_summary = {
        "type": "object",
        "properties": {
            "store_id": {"type": "string", "enum": store_ids},
            "visual_positioning": {"type": "string"},
            "repeatable_codes": _string_array(8),
            "inconsistencies": _string_array(6),
        },
        "required": ["store_id", "visual_positioning", "repeatable_codes", "inconsistencies"],
        "additionalProperties": False,
    }
    hypothesis = {
        "type": "object",
        "properties": {
            "change": {"type": "string"}, "mechanism": {"type": "string"},
            "kpi": {"type": "string"}, "test_design": {"type": "string"},
        },
        "required": ["change", "mechanism", "kpi", "test_design"],
        "additionalProperties": False,
    }
    result = {
        "type": "object",
        "properties": {
            "selection_thesis": {"type": "string"},
            "shared_patterns": _string_array(10),
            "cross_store_differences": _string_array(10),
            "store_summaries": {
                "type": "array", "items": store_summary,
                "minItems": len(store_ids), "maxItems": len(store_ids),
            },
            "recommended_shot_system": _string_array(10),
            "test_hypotheses": {"type": "array", "items": hypothesis, "minItems": 2, "maxItems": 8},
            "images": {
                "type": "array", "items": image_item,
                "minItems": image_count, "maxItems": image_count,
            },
        },
        "required": [
            "selection_thesis", "shared_patterns", "cross_store_differences",
            "store_summaries", "recommended_shot_system", "test_hypotheses", "images",
        ],
        "additionalProperties": False,
    }
    return {"type": "json_schema", "name": "detailed_visual_analysis", "strict": True, "schema": result}


def _data_url(image: DownloadedImage) -> str:
    encoded = base64.b64encode(Path(image.path).read_bytes()).decode("ascii")
    return f"data:{image.mime_type};base64,{encoded}"


def _prompt(filters: dict[str, str]) -> str:
    return (
        "你是一名电商女装视觉策略负责人。请对同一固定维度组合下的多店铺高清商品图做精细视觉分析，"
        "输出中文。先写肉眼可见事实，再写解释；每个判断都要给 visible_cue。不要推断种族、健康、"
        "吸引力等敏感属性。不要把构图相关性写成 CTR/CVR 因果；经营影响只能写成待 A/B 验证的假设。"
        "重点比较：场景、景别、模特动作、光线、色彩、搭配、服装结构呈现、视觉意图、店铺一致性，"
        "并沉淀可复用的 构图-动作-卖点-场景 规则。固定筛选条件："
        + json.dumps(filters, ensure_ascii=False)
    )


class AzureOpenAIDetailedAnalyzer:
    def __init__(
        self, options: AzureOpenAIOptions,
        usage_callback: Callable[[dict], None] | None = None,
    ):
        self.options = options
        self.usage_callback = usage_callback

    def analyze(self, items: list[DetailedVisualItem], filters: dict[str, str]) -> dict:
        if not items:
            raise ValueError("at least one image is required")
        for attempt in range(4):
            try:
                return self._request(items, filters)
            except HTTPError as error:
                if error.code not in RETRY_CODES or attempt == 3:
                    raise
                delay = max(2 ** attempt, float(error.headers.get("Retry-After", 0)))
            except (RemoteDisconnected, TimeoutError, URLError):
                if attempt == 3:
                    raise
                delay = 2 ** attempt
            time.sleep(min(delay, 30))
        raise RuntimeError("Azure OpenAI retry loop exhausted")

    def _request(self, items: list[DetailedVisualItem], filters: dict[str, str]) -> dict:
        content = [{"type": "input_text", "text": _prompt(filters)}]
        for index, item in enumerate(items, 1):
            context = (
                f"IMAGE {index}; store={item.image.store_id}; product={item.image.product_id}; "
                f"title={item.title}; category={item.category}; pixels={item.image.width}x{item.image.height}"
            )
            content.extend([
                {"type": "input_text", "text": context},
                {"type": "input_image", "image_url": _data_url(item.image), "detail": "high"},
            ])
        store_ids = list(dict.fromkeys(item.image.store_id for item in items))
        payload = {
            "model": self.options.deployment,
            "input": [{"role": "user", "content": content}],
            "text": {"format": build_detailed_schema(len(items), store_ids)},
            "max_output_tokens": max(20_000, len(items) * 2_000),
            "store": False,
        }
        request = Request(
            request_url(self.options), data=json.dumps(payload).encode("utf-8"),
            method="POST", headers=self._headers(),
        )
        started = time.perf_counter()
        with urlopen(request, timeout=300) as response:
            body = json.load(response)
        if self.usage_callback:
            self.usage_callback({
                "model": body.get("model") or self.options.deployment,
                "batch_size": len(items), "elapsed_seconds": time.perf_counter() - started,
                "usage": body.get("usage"),
            })
        if body.get("status") == "incomplete":
            reason = (body.get("incomplete_details") or {}).get("reason", "unknown")
            raise RuntimeError(f"Azure OpenAI response incomplete: {reason}")
        result = json.loads(self._output_text(body))
        self._validate_result(result, items, store_ids)
        return result

    def _headers(self) -> dict[str, str]:
        auth = (
            {"api-key": self.options.credential}
            if self.options.auth_type == "api_key"
            else {"Authorization": f"Bearer {self.options.credential}"}
        )
        return {**auth, "Content-Type": "application/json"}

    @staticmethod
    def _output_text(body: dict) -> str:
        for item in body.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    return content["text"]
        raise ValueError(f"Azure OpenAI returned no output text; status={body.get('status', 'unknown')}")

    @staticmethod
    def _validate_result(result: dict, items: list[DetailedVisualItem], store_ids: list[str]) -> None:
        indexes = [row.get("i") for row in result.get("images", [])]
        if sorted(indexes) != list(range(1, len(items) + 1)):
            raise ValueError("model response omitted or duplicated an image index")
        returned_stores = [row.get("store_id") for row in result.get("store_summaries", [])]
        if sorted(returned_stores) != sorted(store_ids):
            raise ValueError("model response omitted or duplicated a store summary")
