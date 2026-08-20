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

from visual_reports import DISPLAY_LABELS


PDF_NAME = "Aloruh纯视觉诊断-图片结论版.pdf"
NOTES_NAME = "Aloruh纯视觉诊断-图片结论版-source-notes.json"
PAGE = landscape((7.5 * inch, 13.333 * inch))
INK = HexColor("#171719")
MUTED = HexColor("#6D6A70")
ACCENT = HexColor("#762C46")
PAPER = HexColor("#F5F0EA")
WHITE = HexColor("#FFFFFF")
LINE = HexColor("#D8D1CB")


def _font() -> str:
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


def _display(value):
    return DISPLAY_LABELS.get(str(value), str(value).replace("_", " "))


def _chinese_summary(value):
    return str(value).replace("Tops", "上衣").replace("Skirts", "半身裙")


def _fetch_image(url, cache_dir):
    parsed = urlparse(str(url))
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("证据图片URL必须使用HTTP或HTTPS")
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{hashlib.sha256(url.encode()).hexdigest()}.jpg"
    if path.is_file():
        return path
    request = urllib.request.Request(url, headers={"User-Agent": "FashionScope/1.0"})
    with urllib.request.urlopen(request, timeout=15) as response:
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
        draw_height = height
        draw_width = height * source_ratio
        draw_x, draw_y = x - (draw_width - width) / 2, y
    else:
        draw_width = width
        draw_height = width / source_ratio
        draw_x, draw_y = x, y - (draw_height - height) / 2
    canvas.saveState()
    clip = canvas.beginPath()
    clip.rect(x, y, width, height)
    canvas.clipPath(clip, stroke=0, fill=0)
    canvas.drawImage(
        ImageReader(str(path)), draw_x, draw_y, draw_width, draw_height,
        preserveAspectRatio=True, mask="auto",
    )
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

    def photo_grid(self, images):
        shown = 0
        for image in images[:12]:
            try:
                path = _fetch_image(image["image_url"], self.cache_dir)
            except Exception as error:
                self.image_failures.append({"url": image.get("image_url"), "error": str(error)})
                continue
            column, row = shown % 6, shown // 6
            _draw_crop(
                self.canvas, path, .45 * inch + column * 2.08 * inch,
                .58 * inch + (1 - row) * 2.55 * inch, 1.94 * inch, 2.4 * inch,
            )
            shown += 1
            if shown == 12:
                break
        return shown

    def finish_page(self):
        self.canvas.showPage()

    def save(self):
        self.canvas.save()


def _metric_label(metric):
    value = metric.get("name") or metric.get("label") or (
        f"{metric.get('row', '')} × {metric.get('column', '')}"
    )
    if " × " in value:
        return " × ".join(_display(part) for part in value.split(" × "))
    return _display(value)


def _draw_summary(deck, report):
    deck.start("执行摘要")
    y = 5.55 * inch
    for title, value in (
        ("样本", f"{report['sample_count']} 张首图"),
        ("范围", "阿洛如（希音）· 上衣与半身裙 · 商品封面图"),
        ("证据", f"{len(report['sections'])}个章节 · 完整源记录编号"),
        ("边界", "不使用曝光、点击、销售或ROI数据"),
    ):
        deck.canvas.setFillColor(PAPER)
        deck.canvas.roundRect(.65 * inch, y - .46 * inch, 5.4 * inch, .68 * inch,
                              .08 * inch, fill=1, stroke=0)
        deck.text(title, .85 * inch, y, 11, ACCENT, 10)
        deck.text(value, 2.15 * inch, y, 11, INK, 44)
        y -= .92 * inch
    deck.text(_chinese_summary(report["summary"]), 6.7 * inch, 4.95 * inch,
              18, INK, 30, 1.5)
    deck.finish_page()


def _draw_heatmaps(deck, report):
    deck.start("视觉焦点与维度组合热力图", "AUDITABLE AGGREGATION")
    focus = report["attention_heatmap"]["cells"][:10]
    maximum = max((cell["count"] for cell in focus), default=1)
    y = 5.55 * inch
    for cell in focus:
        deck.text(_display(cell["label"]), .6 * inch, y, 9, INK, 18)
        deck.canvas.setFillColor(LINE)
        deck.canvas.rect(2.2 * inch, y - 3, 3.6 * inch, 10, fill=1, stroke=0)
        deck.canvas.setFillColor(ACCENT)
        deck.canvas.rect(2.2 * inch, y - 3, 3.6 * inch * cell["count"] / maximum,
                         10, fill=1, stroke=0)
        deck.text(str(cell["count"]), 5.95 * inch, y, 9, MUTED, 8)
        y -= .43 * inch
    pairs = sorted(
        report["combination_heatmap"]["cells"], key=lambda row: row["count"],
        reverse=True,
    )[:12]
    y = 5.55 * inch
    for pair in pairs:
        deck.text(
            f"{_display(pair['row'])} × {_display(pair['column'])}",
            7 * inch, y, 9, INK, 28,
        )
        deck.text(str(pair["count"]), 11.8 * inch, y, 9, ACCENT, 8)
        y -= .43 * inch
    deck.text("计数均可回溯到后附源记录ID，不代表销售热度。", 7 * inch, .65 * inch,
              9, MUTED, 48)
    deck.finish_page()


def _draw_section(deck, section):
    deck.start(section["title"], "SECTION WITH COMPLETE EVIDENCE")
    y = deck.text(section["description"], .55 * inch, 5.75 * inch, 11, MUTED, 90)
    evidence = section["evidence"]
    claim = section["claims"][0]
    y = deck.text(f"结论：{_chinese_summary(claim['conclusion'])}",
                  .55 * inch, y - .18 * inch,
                  16, ACCENT, 72, 1.45)
    y = deck.text(
        f"方法：受控标签聚合 ｜ 样本：{evidence['sample_count']} ｜ "
        f"源记录：{len(evidence['source_records'])}",
        .55 * inch, y - .18 * inch, 9, INK, 90,
    )
    y = deck.text(evidence["analysis_method"], .55 * inch, y, 7, MUTED, 90)
    metrics = "；".join(
        f"{_metric_label(metric)}={metric.get('value', metric.get('count', 0))}"
        for metric in evidence.get("metrics", [])[:12]
    )
    deck.text(f"关键指标：{metrics or '无'}", .55 * inch, y - .08 * inch, 8, MUTED, 120)
    deck.finish_page()
    deck.start(f"{section['title']}｜图片证据", "VISUAL EVIDENCE")
    shown = deck.photo_grid(evidence.get("images", []))
    if shown == 0:
        deck.text("证据图片下载失败；源记录ID仍完整保留在附录。", .75 * inch,
                  3.5 * inch, 14, ACCENT, 60)
    deck.finish_page()


def _draw_record_appendix(deck, records):
    page_size = 22
    for offset in range(0, len(records), page_size):
        deck.start("源记录附录", "COMPLETE EVIDENCE CHAIN")
        y = 5.7 * inch
        for record in records[offset:offset + page_size]:
            product_id = (record.get("image") or {}).get("product_id", "—")
            line = (f"{record['record_id']} | {record['category']} | {product_id} | "
                    f"{record['analysis_method']}")
            deck.text(line, .55 * inch, y, 7.5, INK, 145)
            deck.canvas.setStrokeColor(LINE)
            deck.canvas.line(.55 * inch, y - 6, PAGE[0] - .55 * inch, y - 6)
            y -= .235 * inch
        deck.text(
            f"记录 {offset + 1}–{min(offset + page_size, len(records))} / {len(records)}",
            .55 * inch, .42 * inch, 8, MUTED, 30,
        )
        deck.finish_page()


def build_visual_report(report, output_dir, progress=lambda _stage, _value: None):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    progress("downloading_evidence_images", 15)
    with tempfile.TemporaryDirectory(dir=output_dir) as temporary:
        temporary = Path(temporary)
        pdf_path = temporary / PDF_NAME
        deck = ReportDeck(pdf_path, output_dir / "image_cache")
        deck.start("阿洛如店铺纯视觉诊断", dark=True)
        deck.text(_chinese_summary(report["summary"]), .7 * inch, 3.6 * inch,
                  21, WHITE, 48, 1.5)
        deck.text("网站实时生成 · 最终视觉报告 · 完整证据链", .7 * inch,
                  1.05 * inch, 11, WHITE, 52)
        deck.finish_page()
        _draw_summary(deck, report)
        _draw_heatmaps(deck, report)
        progress("rendering_sections", 45)
        for section in report["sections"]:
            _draw_section(deck, section)
        progress("rendering_evidence_appendix", 75)
        _draw_record_appendix(deck, report["source_records"])
        deck.save()
        generated = datetime.now(timezone.utc).isoformat()
        notes = {
            "generated": generated, "pages": deck.page,
            "aloruh_images": report["sample_count"],
            "tops": sum(row["category"] == "TOPS" for row in report["source_records"]),
            "skirts": sum(row["category"] == "SKIRTS" for row in report["source_records"]),
            "sections": report["sections"],
            "source_records": [row["record_id"] for row in report["source_records"]],
            "excluded_topics": report.get("excluded_metrics", []),
            "image_failures": deck.image_failures,
        }
        notes_path = temporary / NOTES_NAME
        notes_path.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(pdf_path, output_dir / PDF_NAME)
        os.replace(notes_path, output_dir / NOTES_NAME)
    progress("publishing", 95)
    return {
        "report_id": report["report_id"], "generated_at": generated,
        "pages": deck.page, "sample_count": report["sample_count"],
        "image_failures": len(deck.image_failures),
    }
