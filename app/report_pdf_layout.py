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
        self.page_placements = []
        self.sections = {}
        self.observations = {}
        self.used_image_ids = set()
        self.page_used_image_ids = set()
        self.current_spec = None

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

    def _evidence_pool(self, spec, evidence):
        section = self._section(spec)
        claims = [self._claim(spec)] if "claim" in spec else section["claims"]
        ids = []
        for claim in claims:
            claim_evidence = claim["evidence"]
            if evidence in {"all", "support"}:
                ids.extend(claim_evidence["support_image_ids"])
            if evidence in {"all", "counter"}:
                ids.extend(claim_evidence["counterexample_image_ids"])
        return ids

    def _semantic_text(self, image_id):
        observation = self.observations.get(image_id, {})
        observable = observation.get("observable", {})
        values = [value for value in observable.values() if isinstance(value, str)]
        values.extend([
            observation.get("visual_role", ""),
            self.images[image_id].get("title", ""),
        ])
        return " ".join(value for value in values if value)

    def _image_tags(self, image_id):
        tags = set()
        for reason in self.images[image_id].get("selection_reasons", []):
            if reason.get("tag"):
                tags.add(reason["tag"])
            signature = reason.get("signature")
            if isinstance(signature, dict):
                tags.update(value for value in signature.values() if isinstance(value, str))
        return tags

    def _matches(self, image_id, requirements):
        image = self.images[image_id]
        if requirements.get("category") and image.get("category") != requirements["category"]:
            return False
        required_tags = set(requirements.get("tags", []))
        if required_tags and not required_tags.intersection(self._image_tags(image_id)):
            return False
        text = self._semantic_text(image_id)
        if requirements.get("include_any") and not any(word in text for word in requirements["include_any"]):
            return False
        for group in requirements.get("include_groups", []):
            if not any(word in text for word in group):
                return False
        if any(word in text for word in requirements.get("exclude_any", [])):
            return False
        return True

    def _pool(self, spec, requirements=None):
        requirements = requirements or {}
        scope = requirements.get("scope", "claim" if "claim" in spec else "section")
        evidence = requirements.get("evidence", "all")
        if scope == "claim":
            ids = self._evidence_pool(spec, evidence)
        elif scope == "section":
            ids = self._evidence_pool({key: value for key, value in spec.items() if key != "claim"}, evidence)
        elif scope == "store":
            ids = list(self.images)
        else:
            raise ValueError(f"未知图片选择范围: {scope}")
        store = spec.get("store")
        if store:
            ids = [image_id for image_id in ids if self.images[image_id].get("store_id") == store]
        elif self._section(spec)["section_id"] == "competitive_gap":
            ids = [image_id for image_id in ids if self.images[image_id].get("store_id") != "aloruh_shein"]
        else:
            ids = [image_id for image_id in ids if self.images[image_id].get("store_id") == "aloruh_shein"]
        ids = list(dict.fromkeys(ids))
        ids = [image_id for image_id in ids if self._matches(image_id, requirements)]
        ids.sort(key=lambda image_id: (
            image_id in self.page_used_image_ids,
            image_id in self.used_image_ids,
        ))
        if not ids:
            raise ValueError(f"页面 {spec['page']} 没有符合语义条件的证据图: {requirements}")
        return ids

    def _take(self, spec, count, requirements=None):
        requirements = requirements or {}
        pool = self._pool(spec, requirements)
        if len(pool) < count and requirements.get("allow_fewer"):
            selected = pool
        elif len(pool) < count and not requirements.get("allow_repeat", True):
            raise ValueError(f"页面 {spec['page']} 需要 {count} 张图，符合条件的只有 {len(pool)} 张")
        else:
            selected = [pool[index % len(pool)] for index in range(count)]
        self.used_image_ids.update(selected)
        self.page_used_image_ids.update(selected)
        return selected

    def _photo(self, image_id, x, y, width, height, shade=0, slot=None):
        if image_id not in self.images:
            raise ValueError(f"报告引用未知图片: {image_id}")
        path = self.image_loader(self.images[image_id])
        _crop(self.canvas, path, x, y, width, height, shade)
        self.displayed_evidence_ids.append(image_id)
        image = self.images[image_id]
        self.page_placements.append({
            "page": self.page,
            "page_title": self.current_spec["title"],
            "slot": slot or self.current_spec["title"],
            "image_id": image_id,
            "store_id": image.get("store_id"),
            "category": image.get("category"),
            "semantic_text": self._semantic_text(image_id),
        })

    def _grid(self, ids, x, y, width, height, cols, gap=8, shade=0):
        rows = (len(ids) + cols - 1) // cols
        cell_w = (width - gap * (cols - 1)) / cols
        cell_h = (height - gap * (rows - 1)) / rows
        for index, image_id in enumerate(ids):
            col, row = index % cols, index // cols
            draw_x = x + col * (cell_w + gap)
            draw_y = y + (rows - row - 1) * (cell_h + gap)
            self._photo(
                image_id, draw_x, draw_y, cell_w, cell_h, shade,
                f"{self.current_spec['title']} #{index + 1}",
            )

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
        self.observations = {
            row["image_id"]: row for row in report.get("image_observations", [])
        }
        if len(REFERENCE_SEQUENCE) != 53:
            raise RuntimeError("样片页面映射必须固定为53页")
        for spec in REFERENCE_SEQUENCE:
            self.page += 1
            self.current_spec = spec
            self.page_used_image_ids = set()
            self.canvas.setFillColor(INK if spec["kind"] in DARK_KINDS else WHITE)
            self.canvas.rect(0, 0, *PAGE, fill=1, stroke=0)
            getattr(self, f"_draw_{spec['kind']}")(spec)
            self.canvas.showPage()

    def save(self):
        self.canvas.save()
