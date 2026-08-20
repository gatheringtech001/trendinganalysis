from __future__ import annotations

import json
import os
import re
import tempfile
import time
from pathlib import Path


REPORT_SECTION_IDS = (
    "brand_positioning",
    "product_display",
    "store_visual_audit",
    "competitive_gap",
    "visual_upgrade",
)
DETAILED_SECTION_IDS = REPORT_SECTION_IDS
JOB_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


class DetailedReviewStore:
    def __init__(self, root):
        self.root = Path(root)

    def summary(self, job_id):
        job_id = self._validate_job_id(job_id)
        path = self.root / f"{job_id}.json"
        sections = {}
        updated_at = None
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            sections = payload.get("sections", {})
            updated_at = payload.get("updated_at")
        approved = sum(
            sections.get(section_id, {}).get("decision") == "up"
            for section_id in REPORT_SECTION_IDS
        )
        rejected = sum(
            sections.get(section_id, {}).get("decision") == "down"
            for section_id in REPORT_SECTION_IDS
        )
        return {
            "job_id": job_id,
            "total_sections": len(REPORT_SECTION_IDS),
            "reviewed_sections": approved + rejected,
            "approved_sections": approved,
            "rejected_sections": rejected,
            "ready_for_final": approved == len(REPORT_SECTION_IDS),
            "sections": sections,
            "updated_at": updated_at,
        }

    def save(self, job_id, section_id, payload):
        job_id = self._validate_job_id(job_id)
        if section_id not in REPORT_SECTION_IDS:
            raise ValueError("未知的报告专项分析Section")
        if not isinstance(payload, dict) or set(payload) - {"decision", "suggestion"}:
            raise ValueError("审核请求格式不正确")
        decision = payload.get("decision")
        suggestion = str(payload.get("suggestion", "")).strip()
        if decision not in {"up", "down"}:
            raise ValueError("请选择满意或不满意")
        if decision == "down" and not suggestion:
            raise ValueError("不满意时必须填写修改建议")
        if len(suggestion) > 2000:
            raise ValueError("修改建议不能超过2000字")
        current = self.summary(job_id)
        updated_at = self._now()
        current["sections"][section_id] = {
            "decision": decision,
            "suggestion": suggestion if decision == "down" else "",
            "updated_at": updated_at,
        }
        document = {
            "job_id": job_id, "updated_at": updated_at,
            "sections": current["sections"],
        }
        self._atomic_write(self.root / f"{job_id}.json", document)
        return self.summary(job_id)

    def reset(self, job_id, section_id):
        job_id = self._validate_job_id(job_id)
        if section_id not in REPORT_SECTION_IDS:
            raise ValueError("未知的报告专项分析Section")
        current = self.summary(job_id)
        current["sections"].pop(section_id, None)
        updated_at = self._now()
        self._atomic_write(self.root / f"{job_id}.json", {
            "job_id": job_id, "updated_at": updated_at,
            "sections": current["sections"],
        })
        return self.summary(job_id)

    def require_ready(self, job_id):
        review = self.summary(job_id)
        if not review["ready_for_final"]:
            raise ValueError("必须先将报告专项分析的全部Section审核为满意")
        return review

    def attach(self, job):
        return {**job, "review": self.summary(job["job_id"])}

    def _atomic_write(self, path, document):
        self.root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=self.root, delete=False,
        ) as handle:
            json.dump(document, handle, ensure_ascii=False, indent=2)
            temporary = Path(handle.name)
        os.replace(temporary, path)

    @staticmethod
    def _validate_job_id(job_id):
        if not isinstance(job_id, str) or not JOB_ID_PATTERN.fullmatch(job_id):
            raise ValueError("Detailed任务ID不正确")
        return job_id

    @staticmethod
    def _now():
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
