from __future__ import annotations

from pathlib import Path

from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from report_pdf_pages import REFERENCE_SEQUENCE


PAGE = (1920, 1080)
INK = HexColor("#090909")
WHITE = HexColor("#FFFFFF")
PAPER = HexColor("#F5F3EF")
SAND = HexColor("#D2C2B5")
STONE = HexColor("#77726E")
FONT_PATH = Path(__file__).with_name("assets") / "NotoSansSC-Regular-CJK.ttf"
DARK_KINDS = {"dark_collage", "scope", "quote", "brand_feature", "roadmap"}
SECTION_LABELS = {
    "brand_positioning": "品牌现状",
    "product_display": "商品展示分析",
    "store_visual_audit": "店铺视觉分析",
    "competitive_gap": "视觉落差分析",
    "visual_upgrade": "视觉升级方向",
}


def _font(text, bold=False):
    if str(text).isascii():
        return "Helvetica-Bold" if bold else "Helvetica"
    name = "NotoSansSC"
    if name not in pdfmetrics.getRegisteredFontNames():
        if not FONT_PATH.is_file():
            raise RuntimeError(f"PDF中文字体缺失: {FONT_PATH}")
        pdfmetrics.registerFont(TTFont(name, str(FONT_PATH)))
    return name


def _wrap(text, font, size, width):
    lines, current = [], ""
    for char in str(text).replace("\r", ""):
        if char == "\n":
            lines.append(current)
            current = ""
            continue
        candidate = current + char
        if current and pdfmetrics.stringWidth(candidate, font, size) > width:
            lines.append(current)
            current = char
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def _crop(canvas, path, x, y, width, height, shade=0):
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
    canvas.drawImage(ImageReader(str(path)), draw_x, draw_y, draw_width, draw_height, mask="auto")
    if shade:
        canvas.setFillColorRGB(0, 0, 0, alpha=shade)
        canvas.rect(x, y, width, height, fill=1, stroke=0)
    canvas.restoreState()


class DeckBase:
    def __init__(self, path, images, image_loader):
        self.canvas = Canvas(str(path), pagesize=PAGE)
        self.images = images
        self.image_loader = image_loader
        self.page = 0
        self.displayed_evidence_ids = []
        self.sections = {}
        self.cursors = {}

    def _text(self, text, x, y, size, width, color=INK, bold=False, leading=1.16, max_lines=None):
        font = _font(text, bold)
        lines = _wrap(text, font, size, width)
        if max_lines and len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = lines[-1].rstrip("。；，,. ") + "…"
        self.canvas.setFont(font, size)
        self.canvas.setFillColor(color)
        for line in lines:
            self.canvas.drawString(x, y, line)
            y -= size * leading
        return y

    def _section(self, spec):
        section_id = spec.get("section")
        if section_id not in self.sections:
            raise ValueError(f"PDF缺少章节: {section_id}")
        return self.sections[section_id]

    def _claim(self, spec):
        section = self._section(spec)
        index = spec.get("claim", 0)
        if index >= len(section["claims"]):
            raise ValueError(f"章节 {section['section_id']} 缺少第 {index + 1} 条结论")
        return section["claims"][index]

    def _pool(self, spec):
        section = self._section(spec)
        ids = []
        for claim in section["claims"]:
            evidence = claim["evidence"]
            ids.extend(evidence["support_image_ids"])
            ids.extend(evidence["counterexample_image_ids"])
        store = spec.get("store")
        if store:
            ids = [image_id for image_id in ids if self.images[image_id].get("store_id") == store]
        elif section["section_id"] == "competitive_gap":
            ids = [image_id for image_id in ids if self.images[image_id].get("store_id") != "aloruh_shein"]
        desired_store = store or (None if section["section_id"] == "competitive_gap" else "aloruh_shein")
        for image_id, image in self.images.items():
            if desired_store is None or image.get("store_id") == desired_store:
                ids.append(image_id)
        ids = list(dict.fromkeys(ids))
        if not ids:
            raise ValueError(f"页面 {spec['page']} 没有可展示证据图")
        return ids

    def _take(self, spec, count):
        pool = self._pool(spec)
        key = (spec["section"], spec.get("store"))
        start = self.cursors.get(key, 0)
        self.cursors[key] = start + count
        return [pool[(start + index) % len(pool)] for index in range(count)]

    def _photo(self, image_id, x, y, width, height, shade=0):
        if image_id not in self.images:
            raise ValueError(f"报告引用未知图片: {image_id}")
        path = self.image_loader(self.images[image_id]["resolved_url"])
        _crop(self.canvas, path, x, y, width, height, shade)
        self.displayed_evidence_ids.append(image_id)

    def _grid(self, ids, x, y, width, height, cols, gap=8, shade=0):
        rows = (len(ids) + cols - 1) // cols
        cell_w = (width - gap * (cols - 1)) / cols
        cell_h = (height - gap * (rows - 1)) / rows
        for index, image_id in enumerate(ids):
            col, row = index % cols, index // cols
            draw_x = x + col * (cell_w + gap)
            draw_y = y + (rows - row - 1) * (cell_h + gap)
            self._photo(image_id, draw_x, draw_y, cell_w, cell_h, shade)

    def _header(self, spec, dark=False):
        color = WHITE if dark else INK
        self._text(spec["title"], 52, 1015, 28, 1260, color, True, max_lines=2)
        if spec.get("subtitle"):
            self._text(spec["subtitle"], 52, 965, 16, 1200, SAND if dark else STONE, max_lines=2)

    def _body(self, spec):
        return self._claim(spec)["conclusion"] if "claim" in spec else self._section(spec)["summary"]

    def render(self, report):
        self.report = report
        self.sections = {section["section_id"]: section for section in report["sections"]}
        if len(REFERENCE_SEQUENCE) != 53:
            raise RuntimeError("样片页面映射必须固定为53页")
        for spec in REFERENCE_SEQUENCE:
            self.page += 1
            self.canvas.setFillColor(INK if spec["kind"] in DARK_KINDS else WHITE)
            self.canvas.rect(0, 0, *PAGE, fill=1, stroke=0)
            getattr(self, f"_draw_{spec['kind']}")(spec)
            self.canvas.showPage()

    def save(self):
        self.canvas.save()
