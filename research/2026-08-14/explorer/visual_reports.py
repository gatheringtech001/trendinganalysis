from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path


REPORT_ID = "aloruh-visual-diagnostic-2026-08-20"
PDF_NAME = "Aloruh纯视觉诊断-图片结论版.pdf"
SOURCE_NOTES_NAME = "Aloruh纯视觉诊断-图片结论版-source-notes.json"
ANALYSIS_FILES = {
    "TOPS": "image_analysis_tops_cover_aloruh_shein.jsonl",
    "SKIRTS": "image_analysis_skirts_cover_aloruh_shein.jsonl",
}
FOCUS_REGIONS = {
    "NECKLINE": (50, 12), "SHOULDERS": (50, 20), "BACK": (50, 28),
    "SLEEVES": (22, 34), "WAIST": (50, 43), "WAIST_HIP": (50, 52),
    "FABRIC_TEXTURE": (66, 57), "DRAPE": (38, 63), "PRINT": (62, 67),
    "LEGS": (50, 74), "HEMLINE": (50, 88), "FULL_OUTFIT": (50, 50),
}
DISPLAY_LABELS = {
    "NECKLINE": "领口", "SHOULDERS": "肩部", "BACK": "背部", "SLEEVES": "袖部",
    "WAIST": "腰部", "WAIST_HIP": "腰臀", "FABRIC_TEXTURE": "面料纹理",
    "DRAPE": "垂坠感", "PRINT": "印花", "LEGS": "腿部", "HEMLINE": "下摆",
    "FULL_OUTFIT": "整体造型", "FULL_BODY": "全身", "THREE_QUARTER": "四分之三身",
    "HALF_BODY": "半身", "CLOSE_UP": "近景", "DETAIL": "细节特写",
    "FRONT_VIEW": "正面", "SIDE_VIEW": "侧面", "BACK_VIEW": "背面",
    "STANDING": "站姿", "SITTING": "坐姿", "LOOKING_AWAY": "视线移开",
    "MIRROR_SELFIE": "镜面自拍", "INTERACTING_WITH_SCENE": "场景互动",
}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _evidence(records: list[dict], metrics: list[dict], filters: dict) -> dict:
    return {
        "analysis_method": "controlled_taxonomy_aggregation",
        "sample_count": len(records),
        "filters": filters,
        "metrics": metrics,
        "images": [record["image"] for record in records if record.get("image")][:12],
        "source_records": [record["record_id"] for record in records],
    }


class VisualReportCatalog:
    def __init__(self, db_path, pdf_dir, detailed_roots, analysis_dir=None):
        self.db_path = Path(db_path)
        self.pdf_dir = Path(pdf_dir)
        self.detailed_roots = tuple(Path(root) for root in detailed_roots)
        self.analysis_dir = Path(analysis_dir or self.db_path.parent.parent / "data")

    def list_reports(self) -> list[dict]:
        notes = self._notes()
        return [{
            "report_id": REPORT_ID,
            "report_type": "final_visual",
            "title": "Aloruh 店铺纯视觉诊断",
            "generated_at": notes.get("generated", "2026-08-20"),
            "sample_count": notes.get("aloruh_images", 0),
            "pages": notes.get("pages", 0),
            "has_pdf": (self.pdf_dir / PDF_NAME).is_file(),
        }]

    def get(self, report_id: str) -> dict | None:
        if report_id != REPORT_ID:
            return None
        records = self._analysis_records()
        notes = self._notes()
        filters = {"store_id": "aloruh_shein", "position": 1,
                   "product_category": ["TOPS", "SKIRTS"]}
        focus = self._attention_heatmap(records)
        combination = self._combination_heatmap(records)
        versions = Counter(record["analysis_version"] for record in records)
        scope_metrics = [
            {"name": "全部图片", "value": len(records)},
            *({"name": category, "value": sum(
                record["category"] == category for record in records
            )} for category in ANALYSIS_FILES),
        ]
        base = _evidence(records, scope_metrics, filters)
        dominant_focus = max(focus["cells"], key=lambda cell: cell["count"], default=None)
        dominant_pair = max(combination["cells"], key=lambda cell: cell["count"], default=None)
        sections = [
            self._section(
                "scope", "样本范围与口径",
                "报告只使用Aloruh(SHEIN)的Tops与Skirts首图，不使用销售或流量指标。",
                base, [{"claim_id": "scope-count", "conclusion":
                       f"本报告覆盖{len(records)}张首图，其中Tops "
                       f"{scope_metrics[1]['value']}张、Skirts {scope_metrics[2]['value']}张。",
                       "evidence": base}],
            ),
            self._section(
                "attention", "视觉焦点热力分析",
                "依据selling_points标签覆盖率定位画面主要强调的服装区域。",
                _evidence(records, focus["cells"], filters),
                [{"claim_id": "attention-dominant", "conclusion":
                  (f"最常被强调的视觉区域是{DISPLAY_LABELS.get(dominant_focus['label'], dominant_focus['label'])}，覆盖"
                   f"{dominant_focus['count']}张图片。" if dominant_focus else "暂无可识别焦点。"),
                  "evidence": _evidence(records, focus["cells"], filters)}],
            ),
            self._section(
                "combination", "维度组合热力分析",
                "统计画面构图与模特视角动作在同一图片中的共现次数。",
                _evidence(records, combination["cells"], filters),
                [{"claim_id": "combination-dominant", "conclusion":
                  (f"最高频组合是{DISPLAY_LABELS.get(dominant_pair['row'], dominant_pair['row'])} × "
                   f"{DISPLAY_LABELS.get(dominant_pair['column'], dominant_pair['column'])}，"
                   f"共{dominant_pair['count']}张。" if dominant_pair else "暂无可识别组合。"),
                  "evidence": _evidence(records, combination["cells"], filters)}],
            ),
            self._section(
                "coverage", "维度覆盖与分析缺口",
                "区分已分析的12维历史数据与新增3维，禁止把缺失值当作UNKNOWN。",
                _evidence(records, [{"name": key, "value": value}
                                    for key, value in versions.items()], filters),
                [{"claim_id": "coverage-gap", "conclusion":
                  "当前415张历史样本为12维v1分析；光线、模特状态、图文叠加需按v2补分析后才能形成全量结论。",
                  "evidence": _evidence(records, [
                      {"name": "已分析维度", "value": 12},
                      {"name": "待补分析维度", "value": 3},
                  ], filters)}],
            ),
        ]
        return {
            **self.list_reports()[0], "sample_count": len(records),
            "summary": sections[0]["claims"][0]["conclusion"],
            "sections": sections, "attention_heatmap": focus,
            "combination_heatmap": combination,
            "source_records": records,
            "dimension_coverage": {"analyzed": 12, "pending": 3, "target": 15},
            "excluded_metrics": notes.get("excluded_topics", []),
            "approved_detailed": notes.get("approved_detailed"),
        }

    def report_file(self, report_id: str) -> Path | None:
        path = self.pdf_dir / PDF_NAME
        return path if report_id == REPORT_ID and path.is_file() else None

    def list_detailed(self) -> list[dict]:
        rows = []
        seen = set()
        for root in self.detailed_roots:
            candidates = [root] if (root / "result.json").is_file() else (
                list(root.iterdir()) if root.is_dir() else []
            )
            for directory in candidates:
                result_path = directory / "result.json"
                if not directory.is_dir() or not result_path.is_file():
                    continue
                resolved = directory.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                result = _read_json(result_path)
                usage_path = directory / "usage-summary.json"
                rows.append({
                    "job_id": directory.name, "report_type": "detailed_visual",
                    "status": result.get("status", "complete"),
                    "filters": result.get("filters", {}), "stores": result.get("stores", []),
                    "result": result,
                    "usage": _read_json(usage_path) if usage_path.is_file() else None,
                    "updated_at": result_path.stat().st_mtime,
                })
        return sorted(rows, key=lambda row: row["updated_at"], reverse=True)

    def get_detailed(self, job_id) -> dict | None:
        return next(
            (row for row in self.list_detailed() if row["job_id"] == job_id),
            None,
        )

    @staticmethod
    def _section(section_id, title, description, evidence, claims):
        return {"section_id": section_id, "title": title, "description": description,
                "evidence": evidence, "claims": claims}

    def _notes(self) -> dict:
        path = self.pdf_dir / SOURCE_NOTES_NAME
        return _read_json(path) if path.is_file() else {}

    def _analysis_records(self) -> list[dict]:
        lookup = self._image_lookup()
        records = []
        for category, filename in ANALYSIS_FILES.items():
            path = self.analysis_dir / filename
            if not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                analysis = row.get("analysis", {})
                index = int(str(row.get("key", "0")).rsplit(":", 1)[-1])
                image = lookup.get((category, index))
                records.append({
                    "record_id": row.get("key"), "category": category,
                    "analysis_version": analysis.get("analysis_version", ""),
                    "analysis_method": analysis.get("analysis_method", ""),
                    "tags": analysis.get("tags", {}),
                    "confidence": analysis.get("confidence", {}), "image": image,
                })
        return records

    def _image_lookup(self) -> dict:
        if not self.db_path.is_file():
            return {}
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        result = {}
        try:
            for category in ANALYSIS_FILES:
                rows = connection.execute(
                    "SELECT p.product_id, p.title, i.source_url image_url "
                    "FROM products p JOIN images i USING(store_id, product_id) "
                    "WHERE p.store_id='aloruh_shein' AND p.category_group=? AND i.position=1 "
                    "ORDER BY p.product_id", (category,),
                ).fetchall()
                unique = list({row["image_url"]: row for row in rows}.values())
                for index, row in enumerate(unique, 1):
                    result[(category, index)] = dict(row)
        finally:
            connection.close()
        return result

    @staticmethod
    def _attention_heatmap(records):
        counts = Counter(tag for record in records
                         for tag in set(record["tags"].get("selling_points", [])))
        cells = [{"label": tag, "count": count, "share": round(count / len(records), 4),
                  "x": FOCUS_REGIONS.get(tag, (50, 50))[0],
                  "y": FOCUS_REGIONS.get(tag, (50, 50))[1]}
                 for tag, count in counts.most_common() if tag != "UNKNOWN"]
        return {"method": "selling_points image coverage", "cells": cells}

    @staticmethod
    def _combination_heatmap(records):
        pairs = Counter((left, right) for record in records
                        for left in set(record["tags"].get("composition", []))
                        for right in set(record["tags"].get("view_action", []))
                        if "UNKNOWN" not in {left, right})
        rows = [name for name, _ in Counter({key[0]: sum(
            count for pair, count in pairs.items() if pair[0] == key[0]
        ) for key in pairs}).most_common(8)]
        columns = [name for name, _ in Counter({key[1]: sum(
            count for pair, count in pairs.items() if pair[1] == key[1]
        ) for key in pairs}).most_common(8)]
        cells = [{"row": row, "column": column, "count": pairs[(row, column)]}
                 for row in rows for column in columns]
        return {"row_dimension": "composition", "column_dimension": "view_action",
                "rows": rows, "columns": columns, "cells": cells}
