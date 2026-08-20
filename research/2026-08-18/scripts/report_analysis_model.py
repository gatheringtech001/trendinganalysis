from __future__ import annotations

import base64
import json
import time
from http.client import RemoteDisconnected
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from azure_openai_fashion_analyzer import AzureOpenAIOptions, request_url
from high_resolution_images import DownloadedImage


RETRY_CODES = {429, 500, 502, 503, 504}
SECTION_IDS = (
    "brand_positioning", "product_display", "store_visual_audit",
    "competitive_gap", "visual_upgrade",
)
SECTION_TITLES = {
    "brand_positioning": "品牌视觉定位校准",
    "product_display": "商品展示分析",
    "store_visual_audit": "店铺视觉审计",
    "competitive_gap": "竞品视觉差距",
    "visual_upgrade": "视觉升级方向",
}


def _strings(max_items=8, min_items=1):
    return {
        "type": "array", "items": {"type": "string"},
        "minItems": min_items, "maxItems": max_items,
    }


def observation_schema(image_ids: list[str]) -> dict:
    observable = {
        name: {"type": "string"} for name in (
            "scene", "framing", "pose_action", "lighting", "palette",
            "styling", "garment_display", "first_image_type", "brand_signal",
            "text_overlay",
        )
    }
    observation = {
        "type": "object",
        "properties": {
            "image_id": {"type": "string", "enum": image_ids},
            "observable": {
                "type": "object", "properties": observable,
                "required": list(observable), "additionalProperties": False,
            },
            "visual_role": {"type": "string"},
            "strengths": _strings(5), "weaknesses": _strings(5),
            "evidence_cues": _strings(6, 2),
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": [
            "image_id", "observable", "visual_role", "strengths",
            "weaknesses", "evidence_cues", "confidence",
        ],
        "additionalProperties": False,
    }
    pattern = {
        "type": "object",
        "properties": {
            "statement": {"type": "string"},
            "support_image_ids": {
                "type": "array", "items": {"type": "string", "enum": image_ids},
                "minItems": 1, "maxItems": len(image_ids),
            },
            "counterexample_image_ids": {
                "type": "array", "items": {"type": "string", "enum": image_ids},
                "minItems": 0, "maxItems": len(image_ids),
            },
        },
        "required": ["statement", "support_image_ids", "counterexample_image_ids"],
        "additionalProperties": False,
    }
    return {
        "type": "json_schema", "name": "report_image_observations", "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "observations": {
                    "type": "array", "items": observation,
                    "minItems": len(image_ids), "maxItems": len(image_ids),
                },
                "pattern_candidates": {
                    "type": "array", "items": pattern, "minItems": 2, "maxItems": 10,
                },
            },
            "required": ["observations", "pattern_candidates"],
            "additionalProperties": False,
        },
    }


def _claim_schema() -> dict:
    evidence = {
        "type": "object",
        "properties": {
            "support_image_ids": _strings(30),
            "counterexample_image_ids": _strings(20, 0),
            "example_image_ids": _strings(12),
            "observation_fields": _strings(10),
            "sample_count": {"type": "integer", "minimum": 1},
            "filters": {"type": "string"},
        },
        "required": [
            "support_image_ids", "counterexample_image_ids", "example_image_ids",
            "observation_fields", "sample_count", "filters",
        ],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "claim_id": {"type": "string"}, "conclusion": {"type": "string"},
            "derivation": {"type": "string"}, "evidence": evidence,
        },
        "required": ["claim_id", "conclusion", "derivation", "evidence"],
        "additionalProperties": False,
    }


def section_schema(section_ids: list[str] | tuple[str, ...]) -> dict:
    section = {
        "type": "object",
        "properties": {
            "section_id": {"type": "string", "enum": list(section_ids)},
            "title": {"type": "string"}, "summary": {"type": "string"},
            "methodology": {"type": "string"},
            "claims": {
                "type": "array", "items": _claim_schema(), "minItems": 2, "maxItems": 6,
            },
        },
        "required": ["section_id", "title", "summary", "methodology", "claims"],
        "additionalProperties": False,
    }
    return {
        "type": "json_schema", "name": "report_section_analysis", "strict": True,
        "schema": section,
    }


def report_schema() -> dict:
    section = section_schema(SECTION_IDS)["schema"]
    return {
        "type": "json_schema", "name": "visual_diagnostic_report_analysis", "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "executive_summary": _strings(4, 2),
                "sections": {
                    "type": "array", "items": section,
                    "minItems": len(SECTION_IDS), "maxItems": len(SECTION_IDS),
                },
            },
            "required": ["executive_summary", "sections"],
            "additionalProperties": False,
        },
    }


class AzureOpenAIReportAnalyzer:
    def __init__(
        self, options: AzureOpenAIOptions,
        usage_callback: Callable[[dict], None] | None = None,
    ):
        self.options = options
        self.usage_callback = usage_callback

    def analyze_images(self, items: list[dict]) -> dict:
        ids = [item["image_id"] for item in items]
        content = [{"type": "input_text", "text": self._image_prompt()}]
        for item in items:
            image: DownloadedImage = item["download"]
            context = {
                key: item[key] for key in (
                    "image_id", "store_id", "product_id", "category", "role",
                    "selection_reasons",
                )
            }
            content.extend([
                {"type": "input_text", "text": json.dumps(context, ensure_ascii=False)},
                {"type": "input_image", "image_url": self._data_url(image), "detail": "high"},
            ])
        result = self._request(content, observation_schema(ids), len(items), 20_000)
        returned = [row.get("image_id") for row in result.get("observations", [])]
        if sorted(returned) != sorted(ids):
            raise ValueError("report observation response omitted or duplicated an image")
        return result

    def synthesize(self, evidence: dict, scope: dict) -> dict:
        prompt = self._synthesis_prompt(scope) + "\nEVIDENCE:\n" + json.dumps(
            evidence, ensure_ascii=False, separators=(",", ":"),
        )
        result = self._request(
            [{"type": "input_text", "text": prompt}], report_schema(), 0, 30_000,
        )
        self._validate_sections(result["sections"], SECTION_IDS)
        return result

    def revise(self, section: dict, suggestion: str, evidence: dict, scope: dict) -> dict:
        section_id = section["section_id"]
        prompt = (
            "根据审核意见重新分析一个视觉诊断章节。只能使用给定证据，不得编造图片ID。"
            "保留可支持的结论，修改证据不足或表达不清的部分。输出中文。\n"
            f"SECTION={json.dumps(section, ensure_ascii=False)}\n"
            f"REVIEW={suggestion}\nSCOPE={json.dumps(scope, ensure_ascii=False)}\n"
            f"EVIDENCE={json.dumps(evidence, ensure_ascii=False, separators=(',', ':'))}"
        )
        result = self._request(
            [{"type": "input_text", "text": prompt}],
            section_schema([section_id]), 0, 16_000,
        )
        self._validate_sections([result], [section_id])
        return result

    def _request(self, content, schema, batch_size, max_output_tokens):
        payload = {
            "model": self.options.deployment,
            "input": [{"role": "user", "content": content}],
            "text": {"format": schema}, "max_output_tokens": max_output_tokens,
            "store": False,
        }
        for attempt in range(4):
            started = time.perf_counter()
            try:
                request = Request(
                    request_url(self.options), data=json.dumps(payload).encode("utf-8"),
                    method="POST", headers=self._headers(),
                )
                with urlopen(request, timeout=600) as response:
                    body = json.load(response)
                if self.usage_callback:
                    self.usage_callback({
                        "model": body.get("model") or self.options.deployment,
                        "batch_size": batch_size,
                        "elapsed_seconds": time.perf_counter() - started,
                        "usage": body.get("usage"),
                    })
                if body.get("status") == "incomplete":
                    reason = (body.get("incomplete_details") or {}).get("reason", "unknown")
                    raise RuntimeError(f"Azure OpenAI response incomplete: {reason}")
                return json.loads(self._output_text(body))
            except HTTPError as error:
                if error.code not in RETRY_CODES or attempt == 3:
                    raise
                delay = max(2 ** attempt, float(error.headers.get("Retry-After", 0)))
            except (RemoteDisconnected, TimeoutError, URLError):
                if attempt == 3:
                    raise
                delay = 2 ** attempt
            time.sleep(min(delay, 30))
        raise RuntimeError("Azure OpenAI report analysis retry loop exhausted")

    def _headers(self):
        auth = ({"api-key": self.options.credential}
                if self.options.auth_type == "api_key"
                else {"Authorization": f"Bearer {self.options.credential}"})
        return {**auth, "Content-Type": "application/json"}

    @staticmethod
    def _data_url(image):
        value = base64.b64encode(Path(image.path).read_bytes()).decode("ascii")
        return f"data:{image.mime_type};base64,{value}"

    @staticmethod
    def _output_text(body):
        for item in body.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    return content["text"]
        raise ValueError("Azure OpenAI returned no report analysis output text")

    @staticmethod
    def _validate_sections(sections, expected):
        returned = [section.get("section_id") for section in sections]
        if sorted(returned) != sorted(expected):
            raise ValueError("report analysis omitted or duplicated a required section")

    @staticmethod
    def _image_prompt():
        return (
            "你是女装品牌视觉诊断分析师。逐张分析高清商品图，先记录肉眼可见事实，再写优缺点。"
            "不得使用销量、曝光、点击、转化或ROI，不得推断敏感属性。旧分类标签仅是上下文，"
            "不能替代本次观察。证据线索必须能在图片中复核。竞品图只用于对照，不代表目标店铺。"
            "竞品图由全量视觉维度分布分层选出；selection_reasons说明其典型或边界证据角色。"
        )

    @staticmethod
    def _synthesis_prompt(scope):
        roles = "；".join(f"{key}={SECTION_TITLES[key]}" for key in SECTION_IDS)
        return (
            "基于逐图观察与批次模式，生成模仿品牌视觉诊断成品PDF结构的专项分析草稿。"
            "每条结论必须说明推导方法，列支持图、反例图、代表图、样本数和观察字段；"
            "不得引用未提供的图片ID。目标店铺全量图片用于结论，竞品抽样只用于视觉差距。"
            "竞品模式判断必须以competitor_evidence中的全量维度分布为分母，高清代表图只用于"
            "复核典型模式与边界反例，不得把代表图数量冒充全量占比。"
            "不得写销售、流量、点击、转化或ROI结论。五个章节必须各出现一次："
            f"{roles}。范围：{json.dumps(scope, ensure_ascii=False)}"
        )
