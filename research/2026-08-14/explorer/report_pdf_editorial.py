from __future__ import annotations

from pathlib import Path

from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas


PAGE = (1920, 1080)
INK = HexColor("#111111")
WHITE = HexColor("#FFFFFF")
PAPER = HexColor("#F4F1EC")
SAND = HexColor("#D6C6B8")
STONE = HexColor("#706B66")
LINE = HexColor("#D8D3CD")
FONT_PATH = Path(__file__).with_name("assets") / "NotoSansSC-Regular-CJK.ttf"

SECTION_LABELS = {
    "brand_positioning": ("VISUAL POSITIONING", "品牌定位"),
    "product_display": ("PRODUCT DISPLAY", "商品展示"),
    "store_visual_audit": ("STORE VISUAL AUDIT", "店铺视觉"),
    "competitive_gap": ("VISUAL DISCREPANCY", "视觉落差"),
    "visual_upgrade": ("VISUAL UPGRADE", "升级方向"),
}


def _register_font():
    name = "NotoSansSC"
    if name not in pdfmetrics.getRegisteredFontNames():
        if not FONT_PATH.is_file():
            raise RuntimeError(f"PDF中文字体缺失: {FONT_PATH}")
        pdfmetrics.registerFont(TTFont(name, str(FONT_PATH)))
    return name


def _font(text, bold=False):
    if str(text).isascii():
        return "Helvetica-Bold" if bold else "Helvetica"
    return _register_font()


def _wrap(text, font, size, max_width):
    lines, current = [], ""
    for char in str(text).replace("\r", ""):
        if char == "\n":
            lines.append(current)
            current = ""
            continue
        candidate = current + char
        if current and pdfmetrics.stringWidth(candidate, font, size) > max_width:
            lines.append(current)
            current = char
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def _crop(canvas, path, x, y, width, height):
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
    canvas.drawImage(
        ImageReader(str(path)), draw_x, draw_y, draw_width, draw_height,
        preserveAspectRatio=True, mask="auto",
    )
    canvas.restoreState()


class EditorialDeck:
    def __init__(self, path, images, image_loader):
        self.canvas = Canvas(str(path), pagesize=PAGE)
        self.images = images
        self.image_loader = image_loader
        self.page = 0
        self.displayed_evidence_ids = []

    def _new_page(self, background=WHITE):
        self.page += 1
        self.canvas.setFillColor(background)
        self.canvas.rect(0, 0, *PAGE, fill=1, stroke=0)

    def _finish_page(self):
        self.canvas.showPage()

    def _text(self, text, x, y, size, width, color=INK, bold=False,
              leading=1.18, max_lines=None):
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

    def _photo(self, image_id, x, y, width, height):
        image = self.images.get(image_id)
        if image is None:
            raise ValueError(f"报告引用未知图片: {image_id}")
        path = self.image_loader(image["resolved_url"])
        _crop(self.canvas, path, x, y, width, height)

    def cover(self):
        self._new_page()
        self.canvas.setFillColor(INK)
        self.canvas.rect(0, 0, 22, PAGE[1], fill=1, stroke=0)
        self._text("ALORUH", 165, 620, 118, 1200, bold=True)
        self.canvas.setStrokeColor(INK)
        self.canvas.setLineWidth(2)
        self.canvas.line(170, 555, 1040, 555)
        self._text("店铺视觉诊断", 170, 485, 36, 800)
        self._text("VISUAL DIAGNOSTIC · 2026.08", 1430, 95, 18, 390, STONE)
        self._finish_page()

    def executive(self, report):
        self._new_page()
        self._text("VISUAL DIAGNOSTIC", 110, 995, 18, 600, STONE, True)
        self._text("执行摘要", 110, 900, 66, 700)
        for index, summary in enumerate(report["executive_summary"][:4]):
            x = 110 + (index % 2) * 880
            y = 690 - (index // 2) * 340
            self._text(f"0{index + 1}", x, y + 105, 22, 100, SAND, True)
            self._text(summary, x, y, 28, 720, INK, max_lines=5)
        self._finish_page()

    def scope(self, report):
        scope = report["scope"]
        metrics = [
            (scope["target_images"], "ALORUH 全量目标图"),
            (scope.get("competitor_population_images", 0), "三家竞品全量分母"),
            (len(report.get("image_observations", [])), "逐图视觉观察"),
        ]
        self._new_page(PAPER)
        self._text("EVIDENCE SCOPE", 110, 995, 18, 500, STONE, True)
        self._text("证据范围", 110, 915, 58, 650)
        for index, (value, label) in enumerate(metrics):
            x = 110 + index * 590
            self._text(f"{value:,}", x, 735, 72, 480, INK, True)
            self._text(label, x, 650, 20, 450, STONE)
        ids = [row["image_id"] for row in report["images"][:6]]
        for index, image_id in enumerate(ids):
            self._photo(image_id, 110 + index * 286, 80, 258, 420)
        self._finish_page()

    def section_divider(self, section, section_index):
        english, chinese = SECTION_LABELS.get(
            section["section_id"], ("VISUAL DIAGNOSTIC", section["title"]),
        )
        dark = section["section_id"] in {"competitive_gap", "visual_upgrade"}
        background, foreground = (INK, WHITE) if dark else (WHITE, INK)
        self._new_page(background)
        self._text(f"0{section_index}", 110, 965, 24, 120, SAND, True)
        self._text(english, 110, 760, 76, 930, foreground, True, max_lines=2)
        self._text(chinese, 1240, 520, 62, 560, foreground)
        self._text(section["summary"], 110, 320, 24, 950, foreground, max_lines=4)
        self._finish_page()

    def claim(self, section, claim, claim_index):
        self._claim_hero(section, claim, claim_index)
        evidence = claim["evidence"]
        items = [
            (image_id, "支持证据") for image_id in evidence["support_image_ids"]
        ] + [
            (image_id, "边界反例")
            for image_id in evidence["counterexample_image_ids"]
        ]
        for start in range(0, len(items), 12):
            self._evidence_page(section, claim, items[start:start + 12], start // 12 + 1)

    def _claim_hero(self, section, claim, claim_index):
        self._new_page()
        self._text("CLAIM", 100, 990, 17, 120, STONE, True)
        self._text(f"{claim_index:02d}", 100, 920, 44, 180, SAND, True)
        self._text(section["title"], 100, 820, 22, 670, STONE)
        self._text(claim["conclusion"], 100, 735, 36, 690, INK, max_lines=7)
        self._text("如何得到", 100, 330, 16, 140, STONE, True)
        self._text(claim["derivation"], 100, 285, 18, 690, STONE, max_lines=6)
        evidence = claim["evidence"]
        candidates = (
            evidence.get("example_image_ids", [])
            + evidence["support_image_ids"]
            + evidence["counterexample_image_ids"]
        )
        ids = list(dict.fromkeys(candidates))[:3]
        layouts = [(880, 135, 550, 810), (1455, 550, 365, 395), (1455, 135, 365, 395)]
        for image_id, rect in zip(ids, layouts):
            self._photo(image_id, *rect)
        self._finish_page()

    def _evidence_page(self, section, claim, items, part):
        self._new_page(PAPER)
        self._text("IMAGE EVIDENCE", 100, 1000, 16, 300, STONE, True)
        suffix = f" · {part}" if part > 1 else ""
        self._text(f"支持证据 · 边界反例{suffix}", 100, 940, 38, 980)
        self._text(claim["conclusion"], 100, 875, 18, 1600, STONE, max_lines=2)
        tile_width, tile_height = 260, 330
        for index, (image_id, role) in enumerate(items):
            column, row = index % 6, index // 6
            x, y = 100 + column * 295, 485 - row * 410
            self._photo(image_id, x, y, tile_width, tile_height)
            self.canvas.setFillColor(INK if role == "支持证据" else STONE)
            self.canvas.rect(x, y + tile_height - 7, tile_width, 7, fill=1, stroke=0)
            self._text(role, x, y - 27, 14, 105, INK, True)
            meta = self.images[image_id]
            label = f"{meta.get('store_id', '')} · {meta.get('category', '')}"
            self._text(label, x + 112, y - 27, 12, 148, STONE, max_lines=1)
            self.displayed_evidence_ids.append(image_id)
        self._finish_page()

    def closing(self, report):
        self._new_page(INK)
        self._text("FROM VARIETY TO SYSTEM", 110, 965, 18, 700, SAND, True)
        self._text("把丰富视觉资产，\n变成可重复的品牌系统。", 110, 760, 64, 1250, WHITE)
        last = report["sections"][-1]
        self._text(last["summary"], 110, 430, 25, 1050, WHITE, max_lines=4)
        self._text("ALORUH · VISUAL DIAGNOSTIC", 1430, 90, 16, 390, SAND, True)
        self._finish_page()

    def save(self):
        self.canvas.save()
