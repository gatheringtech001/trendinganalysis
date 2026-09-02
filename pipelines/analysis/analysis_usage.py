from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class UsagePricing:
    input_per_million: float
    cached_input_per_million: float
    cache_write_per_million: float
    output_per_million: float
    source: str


TERRA_STANDARD_PRICING = UsagePricing(
    input_per_million=2.0,
    cached_input_per_million=0.2,
    cache_write_per_million=2.5,
    output_per_million=12.0,
    source="OpenAI public standard pricing, 2026-08-18; Azure estimate only",
)

GPT41_STANDARD_PRICING = UsagePricing(
    input_per_million=2.0,
    cached_input_per_million=0.5,
    cache_write_per_million=2.0,
    output_per_million=8.0,
    source=(
        "OpenAI public GPT-4.1 standard pricing; Azure estimate only, "
        "actual regional billing may vary"
    ),
)

SOL_STANDARD_PRICING = UsagePricing(
    input_per_million=5.0,
    cached_input_per_million=0.5,
    cache_write_per_million=6.25,
    output_per_million=30.0,
    source=(
        "OpenAI public standard short-context pricing, 2026-08-19; "
        "Azure estimate only, excludes regional uplift"
    ),
)


def pricing_for_deployment(deployment: str) -> UsagePricing:
    pricing = {
        "gpt-4.1": GPT41_STANDARD_PRICING,
        "gpt-5.6-terra": TERRA_STANDARD_PRICING,
        "gpt-5.6-sol": SOL_STANDARD_PRICING,
    }.get(deployment)
    if pricing is None:
        raise ValueError(f"usage pricing is not configured for {deployment}")
    return pricing

SUMMARY_REPLACE_ATTEMPTS = 20
SUMMARY_RETRY_DELAY_SECONDS = 0.25


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _token(value: object, name: str) -> int:
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


class AnalysisUsageRecorder:
    def __init__(
        self, events_path: Path, summary_path: Path, *, total_images: int,
        deployment: str, pricing: UsagePricing,
    ):
        self.events_path = events_path
        self.summary_path = summary_path
        self.pricing = pricing
        self.lock = threading.Lock()
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        self.summary = self._load_summary(total_images, deployment)
        self._write_summary()

    def _load_summary(self, total_images: int, deployment: str) -> dict:
        if self.summary_path.exists():
            value = json.loads(self.summary_path.read_text(encoding="utf-8"))
            if value.get("deployment") != deployment:
                raise ValueError("usage summary deployment does not match this run")
            if value.get("total_images") != total_images:
                raise ValueError("usage summary image count does not match this run")
            value.update(status="running", finished_at=None)
            return value
        now = _utc_now().isoformat()
        return {
            "status": "running", "deployment": deployment,
            "total_images": total_images, "completed_images": 0,
            "started_at": now, "updated_at": now, "finished_at": None,
            "wall_clock_seconds": 0.0, "api_calls": 0,
            "api_images_submitted": 0, "api_elapsed_seconds": 0.0,
            "input_tokens": 0, "uncached_input_tokens": 0,
            "cached_input_tokens": 0, "cache_write_tokens": 0,
            "output_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0,
            "estimated_cost_usd": 0.0, "pricing": asdict(self.pricing),
        }

    def record(self, event: dict) -> None:
        normalized = self._normalize_event(event)
        with self.lock:
            with self.events_path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(normalized, ensure_ascii=False) + "\n")
            self._accumulate(normalized)
            self._write_summary()

    def _normalize_event(self, event: dict) -> dict:
        usage = event.get("usage")
        if not isinstance(usage, dict):
            raise ValueError("response usage must be an object")
        input_details = usage.get("input_tokens_details") or {}
        output_details = usage.get("output_tokens_details") or {}
        input_tokens = _token(usage.get("input_tokens"), "input_tokens")
        cached = _token(input_details.get("cached_tokens", 0), "cached_tokens")
        cache_write = _token(
            input_details.get("cache_write_tokens", 0), "cache_write_tokens",
        )
        output_tokens = _token(usage.get("output_tokens"), "output_tokens")
        reasoning = _token(
            output_details.get("reasoning_tokens", 0), "reasoning_tokens",
        )
        total_tokens = _token(usage.get("total_tokens"), "total_tokens")
        uncached = max(input_tokens - cached - cache_write, 0)
        cost = (
            uncached * self.pricing.input_per_million
            + cached * self.pricing.cached_input_per_million
            + cache_write * self.pricing.cache_write_per_million
            + output_tokens * self.pricing.output_per_million
        ) / 1_000_000
        return {
            "recorded_at": _utc_now().isoformat(), "model": str(event["model"]),
            "batch_size": _token(event["batch_size"], "batch_size"),
            "elapsed_seconds": round(float(event["elapsed_seconds"]), 4),
            "input_tokens": input_tokens, "uncached_input_tokens": uncached,
            "cached_input_tokens": cached, "cache_write_tokens": cache_write,
            "output_tokens": output_tokens, "reasoning_tokens": reasoning,
            "total_tokens": total_tokens, "estimated_cost_usd": round(cost, 8),
        }

    def _accumulate(self, event: dict) -> None:
        self.summary["api_calls"] += 1
        self.summary["api_images_submitted"] += event["batch_size"]
        for field in (
            "input_tokens", "uncached_input_tokens", "cached_input_tokens",
            "cache_write_tokens", "output_tokens", "reasoning_tokens", "total_tokens",
        ):
            self.summary[field] += event[field]
        self.summary["api_elapsed_seconds"] = round(
            self.summary["api_elapsed_seconds"] + event["elapsed_seconds"], 4,
        )
        self.summary["estimated_cost_usd"] = round(
            self.summary["estimated_cost_usd"] + event["estimated_cost_usd"], 8,
        )

    def finish(self, status: str, *, completed_images: int) -> None:
        if status not in {"complete", "failed"}:
            raise ValueError("status must be complete or failed")
        with self.lock:
            self.summary["status"] = status
            self.summary["completed_images"] = completed_images
            self.summary["finished_at"] = _utc_now().isoformat()
            self._write_summary()

    def _write_summary(self) -> None:
        now = _utc_now()
        started = datetime.fromisoformat(self.summary["started_at"])
        self.summary["updated_at"] = now.isoformat()
        self.summary["wall_clock_seconds"] = round((now - started).total_seconds(), 3)
        building = self.summary_path.with_suffix(self.summary_path.suffix + ".building")
        building.write_text(
            json.dumps(self.summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self._replace_summary(building)

    def _replace_summary(self, building: Path) -> None:
        for attempt in range(SUMMARY_REPLACE_ATTEMPTS):
            try:
                os.replace(building, self.summary_path)
                return
            except PermissionError:
                if attempt == SUMMARY_REPLACE_ATTEMPTS - 1:
                    raise
                time.sleep(SUMMARY_RETRY_DELAY_SECONDS)
