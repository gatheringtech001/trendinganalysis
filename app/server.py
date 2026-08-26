from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import threading
import time
import uuid
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, quote, unquote, urlparse

from data_store import ResearchStore, build_database
from database_builder import SNAPSHOT
from report_pdf import build_visual_report
from report_reviews import DetailedReviewStore, REPORT_SECTION_IDS
from visual_reports import REPORT_ID, VisualReportCatalog


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
DATA_DIR = Path(os.environ.get("FASHION_SCOPE_DATA_DIR", REPO_ROOT / "data"))
DB_PATH = ROOT / "explorer.db"
DIST_DIR = ROOT / "dist"
DEFAULT_ANALYSIS_SCRIPT_DIR = REPO_ROOT / "pipelines" / "analysis"
ANALYSIS_SCRIPT_DIR = Path(os.environ.get(
    "FASHION_SCOPE_ANALYSIS_SCRIPTS", DEFAULT_ANALYSIS_SCRIPT_DIR,
))
if not ANALYSIS_SCRIPT_DIR.is_dir():
    raise RuntimeError(f"analysis scripts directory is missing: {ANALYSIS_SCRIPT_DIR}")
DETAILED_OUTPUT_DIR = Path(os.environ.get(
    "FASHION_SCOPE_DETAILED_OUTPUT_DIR", ROOT / "runtime" / "detailed_visual_jobs",
))
REPORT_ANALYSIS_OUTPUT_DIR = Path(os.environ.get(
    "FASHION_SCOPE_REPORT_ANALYSIS_OUTPUT_DIR", ROOT / "runtime" / "report_analysis_jobs",
))
REPORT_PDF_DIR = Path(os.environ.get(
    "FASHION_SCOPE_REPORT_PDF_DIR", REPO_ROOT / "output" / "pdf",
))
DETAILED_HISTORY_ROOT = Path(os.environ.get(
    "FASHION_SCOPE_DETAILED_HISTORY_ROOT",
    REPO_ROOT / "output" / "visual-analysis-sol-smoke",
))
DETAILED_HISTORY_ROOTS = (
    DETAILED_OUTPUT_DIR,
    DETAILED_HISTORY_ROOT,
)
sys.path.insert(0, str(ANALYSIS_SCRIPT_DIR))

from analyze_dimension_selection import run as run_detailed_analysis
from report_analysis_runner import (
    default_args as report_analysis_args,
    revise_report_section,
    run_report_analysis,
)


class AnalysisBusyError(RuntimeError):
    pass


class DetailedAnalysisJobs:
    def __init__(self, store, db_path, output_root, runner=run_detailed_analysis):
        self.store = store
        self.db_path = Path(db_path)
        self.output_root = Path(output_root)
        self.runner = runner
        self.lock = threading.Lock()
        self.jobs = {}
        self.signatures = {}
        self.active_job_id = None

    def submit(self, payload):
        filters, stores, images_per_store, selected_images = self._validate(payload)
        signature = json.dumps(
            [filters, stores, images_per_store, selected_images],
            ensure_ascii=False, sort_keys=True,
        )
        with self.lock:
            existing_id = self.signatures.get(signature)
            if existing_id and self.jobs[existing_id]["status"] != "failed":
                return {**copy.deepcopy(self.jobs[existing_id]), "reused": True}
            if self.active_job_id:
                raise AnalysisBusyError("已有精细分析任务正在运行，请等待完成")
            job_id = uuid.uuid4().hex
            job = {
                "job_id": job_id, "status": "queued", "stage": "queued",
                "progress": 0, "filters": filters, "stores": stores,
                "images_per_store": images_per_store, "created_at": self._now(),
                "selection_mode": "manual" if selected_images else "random",
                "selected_images": selected_images,
            }
            self.jobs[job_id] = job
            self.signatures[signature] = job_id
            self.active_job_id = job_id
        threading.Thread(
            target=self._execute, args=(job_id, signature), daemon=True,
        ).start()
        return {**copy.deepcopy(job), "reused": False}

    def get(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            return copy.deepcopy(job) if job else None

    def list(self):
        with self.lock:
            return sorted(
                (copy.deepcopy(job) for job in self.jobs.values()),
                key=lambda job: job.get("updated_at", job["created_at"]), reverse=True,
            )

    def _validate(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("request body must be an object")
        filters = payload.get("filters")
        stores = payload.get("stores")
        images_per_store = payload.get("images_per_store", 4)
        selected_images = payload.get("selected_images")
        if not isinstance(filters, dict) or not filters:
            raise ValueError("filters must be a non-empty object")
        if (not isinstance(stores, list) or not stores
                or any(not isinstance(value, str) or not value for value in stores)
                or len(stores) != len(set(stores))):
            raise ValueError("stores must be a non-empty list of unique store IDs")
        if selected_images is None:
            if (isinstance(images_per_store, bool) or not isinstance(images_per_store, int)
                    or not 1 <= images_per_store <= 8
                    or images_per_store * len(stores) > 24):
                raise ValueError("images_per_store must be 1-8 and total images at most 24")
        else:
            selected_images = self._validate_selected_images(selected_images, stores)
        result = self.store.image_dimensions(options={
            "filters": filters, "stores": ",".join(stores),
            "images_per_store": 12 if selected_images else 1,
        })
        if not result["matched_images"]:
            raise ValueError("no analyzed images match the fixed filter combination")
        if selected_images:
            visible = {
                (item["store_id"], item["product_id"], item["position"])
                for group in result.get("store_groups", [])
                for item in group.get("items", [])
            }
            requested = {
                (item["store_id"], item["product_id"], item["position"])
                for item in selected_images
            }
            if not requested <= visible:
                raise ValueError("selected images must come from the displayed filtered results")
        return filters, stores, images_per_store, selected_images

    @staticmethod
    def _validate_selected_images(selected_images, stores):
        if not isinstance(selected_images, list) or not 1 <= len(selected_images) <= 24:
            raise ValueError("selected_images must contain 1-24 images")
        normalized = []
        keys = set()
        for item in selected_images:
            if not isinstance(item, dict) or set(item) != {"store_id", "product_id", "position"}:
                raise ValueError("each selected image must identify store_id, product_id and position")
            store_id = item["store_id"]
            product_id = item["product_id"]
            position = item["position"]
            if (store_id not in stores or not isinstance(product_id, str) or not product_id
                    or isinstance(position, bool) or not isinstance(position, int) or position < 1):
                raise ValueError("selected image identifiers are invalid")
            key = (store_id, product_id, position)
            if key in keys:
                raise ValueError("selected images must be unique")
            keys.add(key)
            normalized.append({
                "store_id": store_id, "product_id": product_id, "position": position,
            })
        return normalized

    def _execute(self, job_id, signature):
        output = self.output_root / job_id
        done = threading.Event()
        monitor = threading.Thread(
            target=self._monitor_manifest, args=(job_id, output, done), daemon=True,
        )
        self._update(job_id, status="running", stage="downloading_hd_images", progress=10)
        monitor.start()
        try:
            job = self.get(job_id)
            args = SimpleNamespace(
                filters=json.dumps(job["filters"], ensure_ascii=False),
                stores=",".join(job["stores"]), db=self.db_path,
                output_root=self.output_root, output=output,
                images_per_store=job["images_per_store"],
                max_images=(len(job["selected_images"])
                            if job["selected_images"]
                            else job["images_per_store"] * len(job["stores"])),
                selected_images=(json.dumps(job["selected_images"], ensure_ascii=False)
                                 if job["selected_images"] else None),
                download_timeout=30, deployment="gpt-5.6-sol",
                endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
                api_key=os.environ.get("AZURE_OPENAI_KEY"), dry_run=False,
            )
            result_dir = self.runner(args)
            done.set()
            monitor.join(timeout=1)
            result = self._read_json(Path(result_dir) / "result.json")
            usage_path = Path(result_dir) / "usage-summary.json"
            usage = self._read_json(usage_path) if usage_path.exists() else None
            for image in result.get("images", []):
                image.pop("path", None)
            self._update(
                job_id, status="complete", stage="complete", progress=100,
                result=result, usage=usage, finished_at=self._now(),
            )
        except Exception as error:
            done.set()
            self._update(
                job_id, status="failed", stage="failed", error=str(error)[:1000],
                finished_at=self._now(),
            )
            with self.lock:
                self.signatures.pop(signature, None)
        finally:
            done.set()
            with self.lock:
                if self.active_job_id == job_id:
                    self.active_job_id = None

    def _monitor_manifest(self, job_id, output, done):
        manifest = output / "manifest.json"
        while not done.wait(0.5):
            if manifest.exists():
                self._update(job_id, stage="sol_visual_analysis", progress=55)
                return

    def _update(self, job_id, **values):
        with self.lock:
            self.jobs[job_id].update(values, updated_at=self._now())

    @staticmethod
    def _read_json(path):
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _now():
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class ReportAnalysisJobs:
    def __init__(
        self, catalog, db_path, output_root, reviews,
        runner=run_report_analysis, revision_runner=revise_report_section,
    ):
        self.catalog = catalog
        self.db_path = Path(db_path)
        self.output_root = Path(output_root)
        self.reviews = reviews
        self.runner = runner
        self.revision_runner = revision_runner
        self.lock = threading.Lock()
        self.jobs = {}
        self.active_job_id = None

    def submit(self, payload):
        target_store, categories = self._validate(payload)
        with self.lock:
            if self.active_job_id:
                raise AnalysisBusyError("已有报告专项分析或修订任务正在运行")
            job_id = uuid.uuid4().hex
            job = {
                "job_id": job_id, "status": "queued", "stage": "queued",
                "progress": 0, "created_at": self._now(), "updated_at": self._now(),
                "scope": {
                    "target_store": target_store, "categories": categories,
                },
            }
            self.jobs[job_id] = job
            self.active_job_id = job_id
            self._persist(job)
        threading.Thread(target=self._run, args=(job_id,), daemon=True).start()
        return copy.deepcopy(job)

    def get(self, job_id):
        with self.lock:
            active = copy.deepcopy(self.jobs.get(job_id))
        row = active or self.catalog.get_report_analysis(job_id)
        return self.reviews.attach(row) if row else None

    def list(self):
        with self.lock:
            active = [copy.deepcopy(row) for row in self.jobs.values()]
        active_ids = {row["job_id"] for row in active}
        persisted = [
            row for row in self.catalog.list_report_analyses()
            if row["job_id"] not in active_ids
        ]
        return [self.reviews.attach(row) for row in active + persisted]

    def revise(self, job_id, section_id, suggestion):
        if section_id not in REPORT_SECTION_IDS:
            raise ValueError("未知的报告专项分析Section")
        if not suggestion.strip():
            raise ValueError("不满意时必须填写修改建议")
        job = self.get(job_id)
        if not job or job.get("status") != "complete":
            raise ValueError("报告专项分析不存在或尚未完成")
        if not any(
            row.get("section_id") == section_id
            for row in (job.get("result") or {}).get("sections", [])
        ):
            raise ValueError("报告专项分析不包含该Section")
        with self.lock:
            if self.active_job_id:
                raise AnalysisBusyError("已有报告专项分析或修订任务正在运行")
            current = self.jobs.get(job_id) or {
                key: value for key, value in job.items() if key != "review"
            }
            current["revision"] = {
                "section_id": section_id, "status": "queued", "progress": 0,
                "suggestion": suggestion.strip(), "started_at": self._now(),
            }
            self.jobs[job_id] = current
            self.active_job_id = job_id
            self._persist(current)
        self.reviews.save(job_id, section_id, {
            "decision": "down", "suggestion": suggestion,
        })
        threading.Thread(
            target=self._revise, args=(job_id, section_id, suggestion.strip()), daemon=True,
        ).start()
        return self.get(job_id)

    def _run(self, job_id):
        job = self.get(job_id)
        scope = job["scope"]
        output = self.output_root / job_id
        self._update(job_id, status="running", stage="selecting_images", progress=2)
        args = report_analysis_args(
            db=self.db_path, output=output, target_store=scope["target_store"],
            categories=scope["categories"],
        )
        try:
            result_dir = self.runner(
                args, lambda stage, progress: self._update(
                    job_id, stage=stage, progress=progress,
                ),
            )
            result = self._read_json(Path(result_dir) / "result.json")
            usage = self._optional_json(Path(result_dir) / "usage-summary.json")
            self._update(
                job_id, status="complete", stage="complete", progress=100,
                result=result, usage=usage, completed_at=self._now(),
            )
        except Exception as error:
            self._update(
                job_id, status="failed", stage="failed", progress=100,
                error=str(error)[:1000], completed_at=self._now(),
            )
        finally:
            with self.lock:
                if self.active_job_id == job_id:
                    self.active_job_id = None

    def _revise(self, job_id, section_id, suggestion):
        output = self.output_root / job_id
        args = report_analysis_args(
            output=output, section_id=section_id, suggestion=suggestion,
        )
        try:
            self.revision_runner(
                args, lambda stage, progress: self._update_revision(
                    job_id, stage=stage, progress=progress,
                ),
            )
            result = self._read_json(output / "result.json")
            revision_usage = self._optional_json(output / "revision-usage-summary.json")
            self.reviews.reset(job_id, section_id)
            self._update(
                job_id, result=result, revision_usage=revision_usage,
                revision={
                    "section_id": section_id, "status": "complete", "progress": 100,
                    "suggestion": suggestion, "completed_at": self._now(),
                },
            )
        except Exception as error:
            self._update_revision(job_id, status="failed", progress=100, error=str(error)[:1000])
        finally:
            with self.lock:
                if self.active_job_id == job_id:
                    self.active_job_id = None

    @staticmethod
    def _validate(payload):
        if not isinstance(payload, dict) or set(payload) - {
            "target_store", "categories",
        }:
            raise ValueError("报告专项分析请求格式不正确")
        target = payload.get("target_store", "aloruh_shein")
        categories = payload.get("categories", ["TOPS", "SKIRTS"])
        if target != "aloruh_shein":
            raise ValueError("当前成品报告模板只支持Aloruh(SHEIN)")
        if (not isinstance(categories, list) or not categories
                or set(categories) - {"TOPS", "SKIRTS"}):
            raise ValueError("报告品类只支持TOPS与SKIRTS")
        return target, list(dict.fromkeys(categories))

    def _update_revision(self, job_id, **values):
        with self.lock:
            revision = self.jobs[job_id].setdefault("revision", {})
            revision.update(values)
            self.jobs[job_id]["updated_at"] = self._now()
            self._persist(self.jobs[job_id])

    def _update(self, job_id, **values):
        with self.lock:
            self.jobs[job_id].update(values, updated_at=self._now())
            self._persist(self.jobs[job_id])

    def _persist(self, job):
        directory = self.output_root / job["job_id"]
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "job.json"
        building = path.with_suffix(".json.building")
        building.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(building, path)

    @staticmethod
    def _read_json(path):
        return json.loads(path.read_text(encoding="utf-8"))

    @classmethod
    def _optional_json(cls, path):
        return cls._read_json(path) if path.is_file() else None

    @staticmethod
    def _now():
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class VisualReportJobs:
    def __init__(self, catalog, output_dir, reviews, runner=build_visual_report):
        self.catalog = catalog
        self.output_dir = Path(output_dir)
        self.reviews = reviews
        self.runner = runner
        self.lock = threading.Lock()
        self.jobs = {}
        self.active_job_id = None

    def submit(self, payload):
        if not isinstance(payload, dict) or set(payload) != {"analysis_job_id"}:
            raise ValueError("必须指定已审核的报告专项分析")
        analysis_job_id = payload["analysis_job_id"]
        analysis = self.catalog.get_report_analysis(analysis_job_id)
        if not analysis or analysis.get("status") != "complete":
            raise ValueError("指定的报告专项分析不存在或尚未完成")
        review = self.reviews.require_ready(analysis_job_id)
        approved_analysis = {
            "job_id": analysis_job_id, "usage": analysis.get("usage"),
            "revision_usage": analysis.get("revision_usage"), "review": review,
            "result": analysis["result"],
        }
        with self.lock:
            if self.active_job_id:
                raise AnalysisBusyError("已有视觉报告正在生成，请等待完成")
            job_id = uuid.uuid4().hex
            job = {
                "job_id": job_id, "status": "queued", "stage": "queued",
                "progress": 0, "created_at": self._now(),
                "analysis_job_id": analysis_job_id,
                "analysis_usage": analysis.get("usage"),
                "revision_usage": analysis.get("revision_usage"),
            }
            self.jobs[job_id] = job
            self.active_job_id = job_id
        threading.Thread(
            target=self._run, args=(job_id, approved_analysis), daemon=True,
        ).start()
        return copy.deepcopy(job)

    def get(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            return copy.deepcopy(job) if job else None

    def list(self):
        with self.lock:
            return [copy.deepcopy(job) for job in reversed(self.jobs.values())]

    def _run(self, job_id, approved_analysis):
        self._update(job_id, status="running", stage="aggregating", progress=5)
        try:
            report = copy.deepcopy(approved_analysis["result"])
            if not report.get("sections") or not report.get("images"):
                raise RuntimeError("报告专项分析缺少章节或图片证据")
            report["approved_analysis"] = {
                key: approved_analysis[key] for key in (
                    "job_id", "usage", "revision_usage", "review",
                )
            }
            result = self.runner(
                report, self.output_dir,
                lambda stage, progress: self._update(
                    job_id, stage=stage, progress=progress,
                ),
            )
            result.setdefault("usage", {
                "api_calls": 0, "input_tokens": 0, "cached_input_tokens": 0,
                "output_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0,
                "estimated_cost_usd": 0,
                "note": "PDF排版在本地完成，未调用模型",
            })
            result["analysis_job_id"] = approved_analysis["job_id"]
            result["analysis_usage"] = approved_analysis.get("usage")
            result["revision_usage"] = approved_analysis.get("revision_usage")
            self._update(
                job_id, status="complete", stage="complete", progress=100,
                completed_at=self._now(), result=result,
            )
        except Exception as error:
            self._update(
                job_id, status="failed", stage="failed", progress=100,
                completed_at=self._now(), error=str(error)[:1000],
            )
        finally:
            with self.lock:
                if self.active_job_id == job_id:
                    self.active_job_id = None

    def _update(self, job_id, **changes):
        with self.lock:
            self.jobs[job_id].update(changes)

    @staticmethod
    def _now():
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class ResearchHandler(SimpleHTTPRequestHandler):
    server_version = "FashionScope/1.0"

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_get(parsed)
            return
        if parsed.path == "/healthz":
            self.send_json({"ok": True, "snapshot": SNAPSHOT})
            return
        if parsed.path != "/" and not (DIST_DIR / parsed.path.lstrip("/")).exists():
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        review_request = self._review_parts(parsed.path)
        report_review_request = self._report_review_parts(parsed.path)
        if parsed.path not in {
            "/api/ask", "/api/detailed-analysis", "/api/report-analyses",
            "/api/reports/generate",
        } and review_request is None and report_review_request is None:
            self.send_error(404)
            return
        declared_length = int(self.headers.get("Content-Length", "0"))
        if declared_length > 16_384:
            self.send_json({"error": "request_too_large"}, 413)
            return
        try:
            payload = json.loads(self.rfile.read(declared_length) or b"{}")
        except json.JSONDecodeError:
            self.send_json({"error": "invalid_json"}, 400)
            return
        if review_request:
            job_id, section_id = review_request
            job = next(
                (row for row in self._detailed_rows() if row["job_id"] == job_id),
                None,
            )
            if not job or job.get("status") != "complete":
                self.send_json({"error": "not_found"}, 404)
                return
            try:
                review = self.server.review_store.save(job_id, section_id, payload)
                self.send_json({**job, "review": review})
            except (TypeError, ValueError) as error:
                self.send_json({"error": "invalid_review", "message": str(error)}, 400)
            return
        if report_review_request:
            job_id, section_id = report_review_request
            try:
                decision = payload.get("decision") if isinstance(payload, dict) else None
                suggestion = str(payload.get("suggestion", "")).strip()
                if decision == "up":
                    review = self.server.review_store.save(job_id, section_id, payload)
                    job = self.server.report_analysis_jobs.get(job_id)
                    self.send_json({**job, "review": review})
                elif decision == "down":
                    self.send_json(
                        self.server.report_analysis_jobs.revise(
                            job_id, section_id, suggestion,
                        ),
                        202,
                    )
                else:
                    raise ValueError("请选择满意或不满意")
            except AnalysisBusyError as error:
                self.send_json({"error": "analysis_busy", "message": str(error)}, 409)
            except (TypeError, ValueError) as error:
                self.send_json({"error": "invalid_review", "message": str(error)}, 400)
            return
        if parsed.path == "/api/reports/generate":
            try:
                self.send_json(self.server.report_jobs.submit(payload), 202)
            except AnalysisBusyError as error:
                self.send_json({"error": "report_busy", "message": str(error)}, 409)
            except (TypeError, ValueError) as error:
                self.send_json({"error": "invalid_request", "message": str(error)}, 400)
            return
        if parsed.path == "/api/detailed-analysis":
            try:
                self.send_json(self.server.analysis_jobs.submit(payload), 202)
            except AnalysisBusyError as error:
                self.send_json({"error": "analysis_busy", "message": str(error)}, 409)
            except (TypeError, ValueError) as error:
                self.send_json({"error": "invalid_request", "message": str(error)}, 400)
            return
        if parsed.path == "/api/report-analyses":
            try:
                self.send_json(self.server.report_analysis_jobs.submit(payload), 202)
            except AnalysisBusyError as error:
                self.send_json({"error": "analysis_busy", "message": str(error)}, 409)
            except (TypeError, ValueError) as error:
                self.send_json({"error": "invalid_request", "message": str(error)}, 400)
            return
        question = str(payload.get("question", ""))[:500]
        self.send_json(self.server.store.answer(question))

    def handle_api_get(self, parsed):
        query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
        store_id = query.get("store", "")
        try:
            if parsed.path == "/api/reports":
                payload = {"items": self.server.reports.list_reports()}
            elif parsed.path == "/api/report-analyses":
                payload = {"items": self.server.report_analysis_jobs.list()}
            elif parsed.path.startswith("/api/report-analyses/"):
                job_id = parsed.path.rsplit("/", 1)[-1]
                payload = self.server.report_analysis_jobs.get(job_id)
                if payload is None:
                    self.send_json({"error": "not_found"}, 404)
                    return
            elif parsed.path == "/api/report-generation":
                payload = {"items": self.server.report_jobs.list()}
            elif parsed.path.startswith("/api/report-generation/"):
                job_id = parsed.path.rsplit("/", 1)[-1]
                payload = self.server.report_jobs.get(job_id)
                if payload is None:
                    self.send_json({"error": "not_found"}, 404)
                    return
            elif parsed.path.startswith("/api/reports/"):
                parts = [unquote(part) for part in parsed.path.split("/")[3:]]
                report_id = parts[0] if parts else ""
                if len(parts) == 2 and parts[1] == "file":
                    path = self.server.reports.report_file(report_id)
                    if path is None:
                        self.send_json({"error": "not_found"}, 404)
                    else:
                        self.send_file(path, "application/pdf")
                    return
                payload = self.server.reports.get(report_id) if len(parts) == 1 else None
                if payload is None:
                    self.send_json({"error": "not_found"}, 404)
                    return
            elif parsed.path == "/api/detailed-analysis":
                payload = {"items": self._detailed_rows()}
            elif parsed.path == "/api/summary":
                payload = self.server.store.summary(store_id)
            elif parsed.path == "/api/engagement":
                payload = self.server.store.engagement(store_id)
            elif parsed.path == "/api/analysis":
                payload = self.server.store.analysis(store_id)
            elif parsed.path == "/api/categories":
                payload = {"items": self.server.store.categories(store_id)}
            elif parsed.path == "/api/products":
                payload = self.server.store.products(
                    store_id, query.get("category", ""), query.get("q", ""),
                    query.get("available") == "1", query.get("page", 1),
                    query.get("page_size", 24), query.get("sort", "rank"),
                )
            elif parsed.path == "/api/images":
                payload = self.server.store.images(
                    store_id, query.get("category", ""), query.get("q", ""),
                    query.get("available") == "1", query.get("page", 1),
                    query.get("page_size", 40),
                )
            elif parsed.path == "/api/image-dimensions":
                payload = self.server.store.image_dimensions(store_id, query)
            elif parsed.path.startswith("/api/detailed-analysis/"):
                job_id = parsed.path.rsplit("/", 1)[-1]
                payload = self.server.analysis_jobs.get(job_id)
                if payload is None:
                    self.send_json({"error": "not_found"}, 404)
                    return
            elif parsed.path.startswith("/api/products/"):
                parts = [unquote(part) for part in parsed.path.split("/")[3:]]
                payload = self.server.store.product_detail(*parts) if len(parts) == 2 else None
                if payload is None:
                    self.send_json({"error": "not_found"}, 404)
                    return
            else:
                self.send_json({"error": "not_found"}, 404)
                return
            self.send_json(payload)
        except (TypeError, ValueError):
            self.send_json({"error": "invalid_query"}, 400)

    def _detailed_rows(self):
        active = self.server.analysis_jobs.list()
        persisted = self.server.reports.list_detailed()
        active_ids = {job["job_id"] for job in active}
        rows = active + [job for job in persisted if job["job_id"] not in active_ids]
        return [self.server.review_store.attach(job) for job in rows]

    @staticmethod
    def _review_parts(path):
        parts = [unquote(part) for part in path.split("/") if part]
        if len(parts) != 5 or parts[:2] != ["api", "detailed-analysis"]:
            return None
        if parts[3] != "reviews":
            return None
        return parts[2], parts[4]

    @staticmethod
    def _report_review_parts(path):
        parts = [unquote(part) for part in path.split("/") if part]
        if len(parts) != 5 or parts[:2] != ["api", "report-analyses"]:
            return None
        if parts[3] != "reviews":
            return None
        return parts[2], parts[4]

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, content_type):
        body = Path(path).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        encoded = quote(Path(path).name)
        self.send_header(
            "Content-Disposition",
            f"inline; filename=aloruh-visual-report.pdf; filename*=UTF-8''{encoded}",
        )
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "private, max-age=300")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")


def main():
    parser = argparse.ArgumentParser(description="Fashion Scope local research site")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4180)
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    if args.rebuild or not DB_PATH.exists():
        print("Building local research database...")
        build_database(DB_PATH, DATA_DIR)
    if args.build_only:
        print(f"Database ready: {DB_PATH.name}")
        return
    if not (DIST_DIR / "index.html").exists():
        raise SystemExit("dist/index.html is missing; run npm install && npm run build")
    handler = partial(ResearchHandler, directory=str(DIST_DIR))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    server.store = ResearchStore(DB_PATH)
    server.analysis_jobs = DetailedAnalysisJobs(
        server.store, DB_PATH, DETAILED_OUTPUT_DIR,
    )
    server.reports = VisualReportCatalog(
        DB_PATH, REPORT_PDF_DIR, DETAILED_HISTORY_ROOTS, analysis_dir=DATA_DIR,
        report_analysis_root=REPORT_ANALYSIS_OUTPUT_DIR,
    )
    server.review_store = DetailedReviewStore(REPORT_PDF_DIR / "reviews")
    server.report_analysis_jobs = ReportAnalysisJobs(
        server.reports, DB_PATH, REPORT_ANALYSIS_OUTPUT_DIR, server.review_store,
    )
    server.report_jobs = VisualReportJobs(
        server.reports, REPORT_PDF_DIR, server.review_store,
    )
    print(f"Fashion Scope: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.store.close()
        server.server_close()


if __name__ == "__main__":
    main()
