from __future__ import annotations

import hashlib
import json
import os
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen.canvas import Canvas

from visual_reports import FINAL_REPORT_NAME, PDF_NAME, REPORT_ID, SOURCE_NOTES_NAME


PAGE = landscape((7.5 * inch, 13.333 * inch))
INK = HexColor("#171719")
MUTED = HexColor("#6D6A70")
ACCENT = HexColor("#762C46")
PAPER = HexColor("#F5F0EA")
WHITE = HexColor("#FFFFFF")
LINE = HexColor("#D8D1CB")


def _font():
    name = "STSong-Light"
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(name))
    return name


def _wrap(text, width):
    lines, current = [], ""
    for char in str(text):
        current += char
        if len(current) >= width or char == "\n":
            lines.append(current.rstrip())
            current = ""
    if current:
        lines.append(current)
    return lines


def _fetch_image(url, cache_dir):
    parsed = urlparse(str(url))
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("证据图片URL必须使用HTTP或HTTPS")
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{hashlib.sha256(url.encode()).hexdigest()}.jpg"
    if path.is_file():
        return path
    request = urllib.request.Request(url, headers={"User-Agent": "FashionScope/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        data = response.read(15_000_001)
    if len(data) > 15_000_000:
        raise ValueError("证据图片超过15MB限制")
    with Image.open(__import__("io").BytesIO(data)) as image:
        image.convert("RGB").save(path, "JPEG", quality=88)
    return path


def _draw_crop(canvas, path, x, y, width, height):
    with Image.open(path) as image:
        source_ratio = image.width / image.height
    target_ratio = width / height
    if source_ratio > target_ratio:
        draw_height, draw_width = height, height * source_ratio
        draw_x, draw_y = x - (draw_width - width) / 2, y
    else:
        draw_width, draw_height = width, width / source_ratio
        draw_x, draw_y = x, y - (draw_height - height) / 2
    canvas.saveState()
    clip = canvas.beginPath()
    clip.rect(x, y, width, height)
    canvas.clipPath(clip, stroke=0, fill=0)
    canvas.drawImage(ImageReader(str(path)), draw_x, draw_y, draw_width, draw_height,
                     preserveAspectRatio=True, mask="auto")
    canvas.restoreState()


class ReportDeck:
    def __init__(self, path, cache_dir):
        self.canvas = Canvas(str(path), pagesize=PAGE)
        self.font = _font()
        self.cache_dir = cache_dir
        self.page = 0
        self.image_failures = []

    def start(self, title, kicker="ALORUH VISUAL DIAGNOSTIC", dark=False):
        self.page += 1
        background, foreground = (INK, WHITE) if dark else (WHITE, INK)
        self.canvas.setFillColor(background)
        self.canvas.rect(0, 0, *PAGE, fill=1, stroke=0)
        self.canvas.setFillColor(foreground)
        self.canvas.setFont("Helvetica", 8)
        self.canvas.drawString(.45 * inch, PAGE[1] - .38 * inch, kicker)
        self.canvas.setFont(self.font, 24)
        self.canvas.drawString(.45 * inch, PAGE[1] - .82 * inch, title)
        self.canvas.setFont(self.font, 7)
        self.canvas.drawRightString(PAGE[0] - .35 * inch, .25 * inch, f"{self.page:02d}")

    def text(self, text, x, y, size=11, color=INK, width=56, leading=1.35):
        self.canvas.setFont("Helvetica" if str(text).isascii() else self.font, size)
        self.canvas.setFillColor(color)
        for line in _wrap(text, width):
            self.canvas.drawString(x, y, line)
            y -= size * leading
        return y

    def photo_grid(self, image_ids, lookup, y=.7 * inch):
        shown = 0
        for image_id in image_ids[:6]:
            image = lookup.get(image_id)
            if not image:
                continue
            try:
                path = _fetch_image(image["resolved_url"], self.cache_dir)
            except Exception as error:
                self.image_failures.append({"image_id": image_id, "error": str(error)})
                continue
            x = .5 * inch + shown * 2.1 * inch
            _draw_crop(self.canvas, path, x, y, 1.92 * inch, 2.55 * inch)
            self.text(image_id, x, y - .16 * inch, 6, MUTED, 26)
            shown += 1
        return shown

    def finish(self):
        self.canvas.showPage()

    def save(self):
        self.canvas.save()


def _approval_summary(report):
    review = report["approved_analysis"]["review"]
    return f"报告专项分析 · {review['approved_sections']}/{review['total_sections']} 章节通过"


def _draw_summary(deck, report):
    deck.start("执行摘要")
    y = 5.55 * inch
    scope = report["scope"]
    competitor_population = scope.get("competitor_population_images")
    competitor_value = (
        f"{competitor_population} 张全量分母 · {scope['competitor_images']} 张分层高清证据"
        if competitor_population is not None
        else f"{scope['competitor_images']} 张旧版分位选图"
    )
    metrics = (
        ("目标样本", f"{scope['target_images']} 张 Aloruh 首图"),
        ("竞品证据", competitor_value),
        ("品类", "上衣与半身裙"),
        ("审核", _approval_summary(report)),
        ("边界", "不使用曝光、点击、转化、销量或ROI"),
    )
    for title, value in metrics:
        deck.canvas.setFillColor(PAPER)
        deck.canvas.roundRect(.65 * inch, y - .46 * inch, 5.4 * inch, .68 * inch,
                              .08 * inch, fill=1, stroke=0)
        deck.text(title, .85 * inch, y, 11, ACCENT, 10)
        deck.text(value, 2.15 * inch, y, 11, INK, 44)
        y -= .92 * inch
    y = 5.2 * inch
    for item in report["executive_summary"]:
        y = deck.text("• " + item, 6.65 * inch, y, 15, INK, 34, 1.5) - .18 * inch
    deck.finish()


def _draw_section(deck, section, lookup):
    deck.start(section["title"], "REPORT SECTION", dark=True)
    deck.text(section["summary"], .7 * inch, 4.65 * inch, 20, WHITE, 48, 1.55)
    deck.text("分析方法", .7 * inch, 2.55 * inch, 9, HexColor("#C9A9B5"), 14)
    deck.text(section["methodology"], .7 * inch, 2.25 * inch, 11, WHITE, 72, 1.4)
    deck.finish()
    for index, claim in enumerate(section["claims"], 1):
        deck.start(f"{section['title']} · 结论 {index}", "CLAIM AND EVIDENCE")
        y = deck.text(claim["conclusion"], .55 * inch, 5.45 * inch, 17, INK, 58, 1.45)
        deck.text("如何得到", .55 * inch, y - .15 * inch, 9, ACCENT, 12)
        deck.text(claim["derivation"], .55 * inch, y - .48 * inch, 10, MUTED, 70, 1.4)
        evidence = claim["evidence"]
        deck.text(f"覆盖 {evidence['sample_count']} 张 · 条件 {evidence['filters']}",
                  7.25 * inch, 5.45 * inch, 10, ACCENT, 55)
        deck.text("观察字段：" + "、".join(evidence["observation_fields"]),
                  7.25 * inch, 5.05 * inch, 9, MUTED, 55)
        deck.text(f"支持 {len(evidence['support_image_ids'])} · 反例 "
                  f"{len(evidence['counterexample_image_ids'])}",
                  7.25 * inch, 4.55 * inch, 10, INK, 55)
        deck.photo_grid(evidence["example_image_ids"], lookup)
        deck.finish()


def _draw_observation_appendix(deck, report):
    observations = report.get("image_observations", [])
    for start in range(0, len(observations), 12):
        deck.start("逐图观察索引", "FULL IMAGE ANALYSIS APPENDIX")
        y = 5.45 * inch
        for row in observations[start:start + 12]:
            cues = "；".join(row.get("evidence_cues", [])[:2])
            deck.text(row["image_id"], .55 * inch, y, 8, ACCENT, 24)
            deck.text(row.get("visual_role", ""), 2.15 * inch, y, 9, INK, 38)
            deck.text(cues, 6.2 * inch, y, 8, MUTED, 88)
            deck.canvas.setStrokeColor(LINE)
            deck.canvas.line(.55 * inch, y - .12 * inch, PAGE[0] - .55 * inch, y - .12 * inch)
            y -= .43 * inch
        deck.finish()


def build_visual_report(report, output_dir, progress=lambda _stage, _value: None):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    lookup = {row["image_id"]: row for row in report["images"]}
    progress("rendering_cover", 10)
    with tempfile.TemporaryDirectory(dir=output_dir) as temporary_name:
        temporary = Path(temporary_name)
        pdf_path = temporary / PDF_NAME
        deck = ReportDeck(pdf_path, output_dir / "image_cache")
        deck.start("ALORUH", "VISUAL DIAGNOSTIC", dark=True)
        deck.text("店铺视觉诊断", .7 * inch, 3.65 * inch, 30, WHITE, 28)
        deck.text("专项视觉分析 · 逐结论证据链", .7 * inch, 3.08 * inch, 13,
                  HexColor("#C9A9B5"), 36)
        deck.finish()
        _draw_summary(deck, report)
        progress("rendering_sections", 25)
        for index, section in enumerate(report["sections"]):
            _draw_section(deck, section, lookup)
            progress("rendering_sections", 25 + round((index + 1) / len(report["sections"]) * 45))
        progress("rendering_evidence_appendix", 75)
        _draw_observation_appendix(deck, report)
        deck.save()
        generated = datetime.now(timezone.utc).isoformat()
        final = {
            "report_id": REPORT_ID, "report_type": "final_visual",
            "title": "Aloruh 店铺视觉诊断", "generated_at": generated,
            "pages": deck.page, "sample_count": report["scope"]["target_images"],
            "summary": report["executive_summary"], "scope": report["scope"],
            "sections": report["sections"], "images": report["images"],
            "image_observations": report.get("image_observations", []),
            "approved_analysis": report["approved_analysis"],
        }
        notes = {**final, "image_failures": deck.image_failures,
                 "usage": {"total_tokens": 0, "estimated_cost_usd": 0,
                           "note": "最终PDF仅做本地排版，未调用模型"}}
        notes_path = temporary / SOURCE_NOTES_NAME
        final_path = temporary / FINAL_REPORT_NAME
        notes_path.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
        final_path.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
        progress("publishing", 95)
        os.replace(pdf_path, output_dir / PDF_NAME)
        os.replace(notes_path, output_dir / SOURCE_NOTES_NAME)
        os.replace(final_path, output_dir / FINAL_REPORT_NAME)
    progress("complete", 100)
    return {"report_id": REPORT_ID, "generated_at": generated, "pages": deck.page,
            "sample_count": report["scope"]["target_images"],
            "analysis_job_id": report["approved_analysis"]["job_id"],
            "usage": notes["usage"], "image_failures": deck.image_failures}
