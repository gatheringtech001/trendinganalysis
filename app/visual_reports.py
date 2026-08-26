from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path


REPORT_ID = "aloruh-visual-diagnostic-2026-08-20"
PDF_NAME = "Aloruh纯视觉诊断-图片结论版.pdf"
SOURCE_NOTES_NAME = "Aloruh纯视觉诊断-图片结论版-source-notes.json"
FINAL_REPORT_NAME = "Aloruh纯视觉诊断-图片结论版.json"
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
    def __init__(
        self, db_path, pdf_dir, detailed_roots, analysis_dir=None,
        report_analysis_root=None,
    ):
        self.db_path = Path(db_path)
        self.pdf_dir = Path(pdf_dir)
        self.detailed_roots = tuple(Path(root) for root in detailed_roots)
        self.analysis_dir = Path(analysis_dir or self.db_path.parent.parent / "data")
        self.report_analysis_root = Path(
            report_analysis_root or self.db_path.parent / "runtime" / "report_analysis_jobs",
        )

    def list_reports(self) -> list[dict]:
        report = self._final_report()
        if report is None:
            return []
        return [{key: report.get(key) for key in (
            "report_id", "report_type", "title", "generated_at", "sample_count", "pages",
        )} | {"has_pdf": (self.pdf_dir / PDF_NAME).is_file()}]

    def get(self, report_id: str) -> dict | None:
        if report_id != REPORT_ID:
            return None
        report = self._final_report()
        return {**report, "has_pdf": (self.pdf_dir / PDF_NAME).is_file()} if report else None

    def list_report_analyses(self) -> list[dict]:
        if not self.report_analysis_root.is_dir():
            return []
        rows = []
        for directory in self.report_analysis_root.iterdir():
            row = self.get_report_analysis(directory.name)
            if row:
                rows.append(row)
        return sorted(rows, key=lambda row: row.get("updated_at", ""), reverse=True)

    def get_report_analysis(self, job_id: str) -> dict | None:
        if not isinstance(job_id, str) or not job_id.replace("-", "").isalnum():
            return None
        directory = self.report_analysis_root / job_id
        result_path = directory / "result.json"
        job_path = directory / "job.json"
        if not result_path.is_file() and not job_path.is_file():
            return None
        row = _read_json(job_path) if job_path.is_file() else {"job_id": job_id}
        if result_path.is_file():
            result = _read_json(result_path)
            row.update(status=result.get("status", "complete"), result=result)
        usage = directory / "usage-summary.json"
        revision_usage = directory / "revision-usage-summary.json"
        row["usage"] = _read_json(usage) if usage.is_file() else None
        row["revision_usage"] = _read_json(revision_usage) if revision_usage.is_file() else None
        return row

    def report_file(self, report_id: str) -> Path | None:
        path = self.pdf_dir / PDF_NAME
        return path if report_id == REPORT_ID and path.is_file() else None

    def _final_report(self) -> dict | None:
        path = self.pdf_dir / FINAL_REPORT_NAME
        return _read_json(path) if path.is_file() else None

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
