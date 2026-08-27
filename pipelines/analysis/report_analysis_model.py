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
OBSERVABLE_FIELDS = (
    "scene", "framing", "pose_action", "lighting", "palette", "styling",
    "silhouette", "design_details", "material_texture", "garment_display",
    "first_image_type", "brand_signal", "text_overlay", "model_presence",
    "face_visibility", "hairstyle", "makeup_presentation", "expression_gaze",
)
SECTION_EVIDENCE_FIELDS = {
    "brand_positioning": (
        "scene", "lighting", "palette", "styling", "first_image_type",
        "brand_signal", "text_overlay",
    ),
    "product_display": (
        "framing", "pose_action", "styling", "silhouette", "design_details",
        "material_texture", "garment_display", "first_image_type",
    ),
    "store_visual_audit": (
        "scene", "framing", "pose_action", "lighting", "palette", "styling",
        "first_image_type", "brand_signal", "text_overlay", "model_presence",
        "face_visibility", "hairstyle", "makeup_presentation", "expression_gaze",
    ),
    "competitive_gap": (
        "scene", "framing", "pose_action", "lighting", "palette", "styling",
        "garment_display", "first_image_type", "brand_signal", "text_overlay",
    ),
}
SECTION_EVIDENCE_ROLES = {
    "brand_positioning": {"target"},
    "product_display": {"target"},
    "store_visual_audit": {"target"},
    "competitive_gap": {"competitor"},
}
MAX_SECTION_PATTERNS = 80
MAX_COMPETITOR_CLUSTERS = 12


def _summary_schema() -> dict:
    return {
        "type": "json_schema", "name": "report_executive_summary", "strict": True,
        "schema": {
            "type": "object",
            "properties": {"executive_summary": _strings(4, 2)},
            "required": ["executive_summary"], "additionalProperties": False,
        },
    }


def _compact_context(context: dict) -> dict:
    title = str(context.get("title") or "")[:160]
    return {
        "image_id": context.get("image_id"),
        "store_id": context.get("store_id"),
        "product_id": context.get("product_id"),
        "position": context.get("position"),
        "title": title,
        "role": context.get("role"),
        "category": context.get("category"),
        "selection_reasons": (context.get("selection_reasons") or [])[:4],
    }


def _compact_competitor_evidence(evidence: dict) -> dict:
    result = {
        key: evidence.get(key) for key in ("method", "dimensions", "categories")
        if key in evidence
    }
    stores = {}
    for store_id, store in (evidence.get("stores") or {}).items():
        compact_store = {
            key: store.get(key)
            for key in ("population_images", "analyzed_images", "selected_images")
            if key in store
        }
        categories = {}
        for category, plan in (store.get("categories") or {}).items():
            compact_plan = {
                key: plan.get(key)
                for key in (
                    "status", "population_images", "analyzed_images",
                    "selected_images", "dimensions",
                )
                if key in plan
            }
            if "visual_clusters" in plan:
                compact_plan["visual_clusters"] = plan["visual_clusters"][
                    :MAX_COMPETITOR_CLUSTERS
                ]
            categories[category] = compact_plan
        if categories:
            compact_store["categories"] = categories
        stores[store_id] = compact_store
    result["stores"] = stores
    return result


def _section_evidence(
    evidence: dict, section_id: str, prior_sections: list[dict] | None = None,
) -> dict:
    if section_id == "visual_upgrade":
        return {
            "prior_sections": prior_sections or [],
            "evidence_note": "升级建议只回指前四章已经验证的结论及其图片证据。",
        }
    fields = SECTION_EVIDENCE_FIELDS[section_id]
    roles = SECTION_EVIDENCE_ROLES[section_id]
    contexts = {
        row.get("image_id"): row for row in evidence.get("image_contexts", [])
        if row.get("role") in roles
    }
    observations = []
    for row in evidence.get("observations", []):
        image_id = row.get("image_id")
        if image_id not in contexts:
            continue
        observable = row.get("observable") or {}
        observations.append({
            "image_id": image_id,
            "observable": {name: observable.get(name, "") for name in fields},
            "visual_role": row.get("visual_role", ""),
            "strengths": (row.get("strengths") or [])[:3],
            "weaknesses": (row.get("weaknesses") or [])[:3],
            "evidence_cues": (row.get("evidence_cues") or [])[:4],
            "confidence": row.get("confidence"),
        })
    known_ids = set(contexts)
    patterns = []
    for row in evidence.get("pattern_candidates", []):
        support = [value for value in row.get("support_image_ids", []) if value in known_ids]
        if not support:
            continue
        counter = [
            value for value in row.get("counterexample_image_ids", [])
            if value in known_ids
        ]
        patterns.append({
            "statement": row.get("statement", ""),
            "support_image_ids": support[:12],
            "counterexample_image_ids": counter[:6],
        })
        if len(patterns) >= MAX_SECTION_PATTERNS:
            break
    result = {
        "observations": observations,
        "pattern_candidates": patterns,
        "image_contexts": [_compact_context(row) for row in contexts.values()],
        "evidence_note": (
            "所有入选高清图均已逐图分析；这里只按章节裁剪角色和观察字段，"
            "不是再次抽样。"
        ),
    }
    if section_id == "competitive_gap":
        result["competitor_evidence"] = _compact_competitor_evidence(
            evidence.get("competitor_evidence", {}),
        )
    return result


def _strings(max_items=8, min_items=1):
    return {
        "type": "array", "items": {"type": "string"},
        "minItems": min_items, "maxItems": max_items,
    }


def observation_schema(image_ids: list[str]) -> dict:
    observable = {
        name: {"type": "string"} for name in OBSERVABLE_FIELDS
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
                    "image_id", "store_id", "product_id", "position", "title",
                    "role", "selection_reasons",
                )
            }
            context["category"] = item["category_group"]
            content.extend([
                {"type": "input_text", "text": json.dumps(context, ensure_ascii=False)},
                {"type": "input_image", "image_url": self._data_url(image), "detail": "high"},
            ])
        result = self._request(content, observation_schema(ids), len(items), 20_000)
        returned = [row.get("image_id") for row in result.get("observations", [])]
        if sorted(returned) != sorted(ids):
            raise ValueError("report observation response omitted or duplicated an image")
        return result

    def synthesize(
        self, evidence: dict, scope: dict, checkpoint_dir: Path | None = None,
    ) -> dict:
        checkpoints = Path(checkpoint_dir) if checkpoint_dir else None
        if checkpoints:
            checkpoints.mkdir(parents=True, exist_ok=True)
        sections = []
        for section_id in SECTION_IDS:
            path = checkpoints / f"{section_id}.json" if checkpoints else None
            if path and path.is_file():
                section = json.loads(path.read_text(encoding="utf-8"))
            else:
                focused = _section_evidence(evidence, section_id, sections)
                prompt = self._section_prompt(scope, section_id) + "\nEVIDENCE:\n" + json.dumps(
                    focused, ensure_ascii=False, separators=(",", ":"),
                )
                section = self._request(
                    [{"type": "input_text", "text": prompt}],
                    section_schema([section_id]), 0, 10_000,
                )
                if path:
                    self._write_checkpoint(path, section)
            self._validate_sections([section], [section_id])
            sections.append(section)
        summary_path = checkpoints / "executive_summary.json" if checkpoints else None
        if summary_path and summary_path.is_file():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        else:
            summary = self._request(
                [{
                    "type": "input_text",
                    "text": (
                        "根据五个已验证章节写2至4条中文执行摘要。不得增加新事实或图片ID。\n"
                        f"SECTIONS={json.dumps(sections, ensure_ascii=False, separators=(',', ':'))}"
                    ),
                }],
                _summary_schema(), 0, 4_000,
            )
            if summary_path:
                self._write_checkpoint(summary_path, summary)
        result = {"executive_summary": summary["executive_summary"], "sections": sections}
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
    def _write_checkpoint(path: Path, value: dict) -> None:
        building = path.with_suffix(path.suffix + ".building")
        building.write_text(
            json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        building.replace(path)

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
            "竞品图只从已完成12维标签覆盖的可比品类全量分布中分层选出；"
            "未覆盖品类不得推断。selection_reasons说明其典型或边界证据角色。"
            "模特相关字段只记录实际可见的在场人数、面部可见性、发型、妆容表现、表情和视线；"
            "不可见时写不可观察。禁止推断年龄、种族、国籍、身高、体型尺寸、健康或吸引力。"
            "产品字段要分别记录廓形、可见设计细节、可见材质纹理和商品展示完整度。"
            "同一product_id的position 1与2属于同一商品，必须分别观察后再判断多视角展示，"
            "不得仅凭图片顺序假定正面或背面。"
        )

    @staticmethod
    def _synthesis_prompt(scope):
        roles = "；".join(f"{key}={SECTION_TITLES[key]}" for key in SECTION_IDS)
        return (
            "基于逐图观察与批次模式，生成模仿品牌视觉诊断成品PDF结构的专项分析草稿。"
            "每条结论必须说明推导方法，列支持图、反例图、代表图、样本数和观察字段；"
            "不得引用未提供的图片ID。商品数与品类占比来自目标店铺全量目录；"
            "视觉结论只代表重点品类的可复现随机样本，不得外推为目标店铺全部图片。"
            "primary_categories是前三大重点品类，supplementary_categories是白皮书重点补充品类；"
            "商品展示章节逐一覆盖primary_categories，补充品类用于风格、布景、搭配和升级方向交叉验证。"
            "竞品高清分层证据集只用于视觉差距。"
            "竞品模式判断必须以competitor_evidence中的全量维度分布为分母，高清代表图只用于"
            "复核典型模式与边界反例，不得把代表图数量冒充全量占比。"
            "竞品只允许比较categories中status=available且具有完整12维标签的品类；"
            "dimension_tags_unavailable或category_unavailable必须在结论中明确披露，"
            "不得用其他品类代替，也不得把未覆盖品类写成已比较。"
            "competitive_gap必须分别包含Princess Polly、Motel Rocks、PrettyLittleThing三家品牌，"
            "每家至少一条独立结论；结论或推导必须写出品牌名，支持图或代表图必须来自该品牌。"
            "不得写销售、流量、点击、转化或ROI结论。五个章节必须各出现一次："
            f"{roles}。brand_positioning必须说明店铺基本信息、全量重点品类和风格划分；"
            "product_display必须分别分析每个重点品类的可复现随机样本，并覆盖卖点、动作和搭配；"
            "store_visual_audit必须覆盖拍摄布景、拍摄风格及仅限可见属性的模特画像；"
            "competitive_gap只比较当前采集的三家竞品，并保持逐品牌证据隔离；"
            "visual_upgrade必须回指前四章证据。人群画像和代表红人不在分析范围内。"
            f"范围：{json.dumps(scope, ensure_ascii=False)}"
        )

    @staticmethod
    def _section_prompt(scope: dict, section_id: str) -> str:
        requirements = {
            "brand_positioning": (
                "说明店铺基本信息、全量重点品类、视觉风格划分与品牌信号；"
                "商品数和品类占比可引用全量目录，视觉判断只能引用目标店逐图证据。"
            ),
            "product_display": (
                "分别覆盖前三重点品类，并用补充品类交叉验证产品卖点、动作、常见搭配、"
                "廓形、设计细节、材质纹理和多视角展示。不得按position顺序猜正背面。"
            ),
            "store_visual_audit": (
                "覆盖拍摄布景、拍摄风格、光线、构图、图文叠加和可见模特画像；"
                "模特只记录人数、面部可见性、发型、妆容、表情和视线。"
            ),
            "competitive_gap": (
                "分别写Princess Polly、Motel Rocks、PrettyLittleThing，至少每家一条独立结论；"
                "支持图或代表图必须属于该品牌。全量标签分布是统计分母，高清图只复核典型与边界。"
            ),
            "visual_upgrade": (
                "只根据前四章已验证结论提出升级方向，并复用其有效图片ID；"
                "每条建议要说明对应问题、证据和预期视觉改进，不得杜撰新观察。"
            ),
        }
        return (
            "所有入选高清图已完成逐图观察。现在只生成一个视觉诊断章节，输出中文，"
            "不得引用未提供的图片ID。每条结论必须说明推导方法，并列出支持图、反例图、"
            "代表图、样本数、筛选条件和观察字段。不得写销量、曝光、点击、转化或ROI，"
            "不得推断敏感属性、人群画像或代表红人。"
            f"章节={section_id}({SECTION_TITLES[section_id]})。要求：{requirements[section_id]}"
            f"范围：{json.dumps(scope, ensure_ascii=False, separators=(',', ':'))}"
        )
