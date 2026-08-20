from __future__ import annotations

import io
import hashlib
import json
import sqlite3
import urllib.request
from collections import Counter
from pathlib import Path

from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas


ROOT = Path(__file__).parents[3]
DB = ROOT / "research/2026-08-14/explorer/explorer.db"
DATA = ROOT / "research/2026-08-14/data"
OUT = ROOT / "output/pdf/Aloruh纯视觉诊断.pdf"
NOTES = ROOT / "output/pdf/Aloruh纯视觉诊断-source-notes.json"
CACHE = ROOT / "tmp/pdfs/aloruh-visual-report/images"
PAGE = landscape((7.5 * inch, 13.333 * inch))
INK, MUTED, BG = HexColor("#201B1C"), HexColor("#756B6C"), HexColor("#F5F0EA")
ACCENT, PINK, GOLD, WHITE = HexColor("#7A233E"), HexColor("#D694A8"), HexColor("#B88A46"), HexColor("#FFFFFF")
DIMENSIONS = [
    ("product_category", "商品类别"), ("silhouette_fit", "廓形版型"),
    ("design_elements", "设计元素"), ("occasion", "穿着场景"),
    ("composition", "画面构图"), ("view_action", "视角动作"),
    ("selling_points", "卖点部位"), ("scene", "拍摄场景"),
    ("material_texture", "材质纹理"), ("color_pattern", "色彩图案"),
    ("visual_language", "视觉语言"), ("styling", "搭配方式"),
]
ZH = {
    "TOPS":"上衣", "SKIRTS":"裙装", "SHORTS":"短裤", "SETS":"套装", "FITTED":"修身", "DRAPED":"垂坠",
    "RELAXED":"宽松", "CORSETED":"束身", "FLARED":"伞摆", "SLIM":"窄身", "A_LINE":"A字",
    "HALTER":"挂脖", "EMBELLISHED":"装饰", "SPAGHETTI_STRAP":"细肩带", "ASYMMETRIC":"不对称",
    "SHEER_PANEL":"透视拼接", "BACKLESS":"露背", "RUCHED":"抽褶", "TIE_DETAIL":"系带",
    "GOING_OUT":"外出", "DATE_NIGHT":"约会", "VACATION":"度假", "PARTY":"派对", "CASUAL":"休闲",
    "BEACH":"海滩", "COMMUTE":"通勤", "FESTIVAL":"节庆", "THREE_QUARTER":"四分之三身",
    "HALF_BODY":"半身", "FULL_BODY":"全身", "CLOSE_UP":"近景", "PRODUCT_ONLY":"仅商品",
    "DETAIL":"细节", "FLAT_LAY":"平铺", "STANDING":"站姿", "FRONT_VIEW":"正面",
    "LOOKING_AWAY":"视线移开", "MIRROR_SELFIE":"镜面自拍", "SITTING":"坐姿", "SIDE_VIEW":"侧面",
    "BACK_VIEW":"背面", "INTERACTING_WITH_SCENE":"场景互动", "NECKLINE":"领口", "WAIST":"腰线",
    "SHOULDERS":"肩部", "FABRIC_TEXTURE":"面料纹理", "DRAPE":"垂坠", "PRINT":"印花",
    "HEMLINE":"下摆", "SLEEVES":"袖型", "STUDIO_NEUTRAL":"中性棚拍", "HOME":"室内家居",
    "MIRROR":"镜面", "ARCHITECTURE":"建筑空间", "OTHER":"其他", "STREET":"街景", "NATURE":"自然",
    "LACE":"蕾丝", "UNKNOWN":"未识别", "MESH":"网纱", "CHIFFON":"雪纺", "KNIT":"针织", "SATIN_LIKE":"缎面感",
    "SEQUIN":"亮片", "RIBBED":"罗纹", "COTTON_LIKE":"棉感", "PATTERN_SOLID":"纯色",
    "COLOR_BLACK":"黑色", "COLOR_WHITE":"白色", "COLOR_BROWN":"棕色", "COLOR_BLUE":"蓝色",
    "PATTERN_FLORAL":"花卉", "COLOR_BEIGE":"米色", "COLOR_RED":"红色", "NATURAL_LIGHT":"自然光",
    "SOCIAL_UGC":"社交UGC", "LIFESTYLE":"生活方式", "SOFT_LIGHT":"柔光", "GLAMOROUS":"华丽",
    "ECOMMERCE_CLEAN":"电商净图", "MINIMAL":"极简", "WARM_TONE":"暖调", "FULL_LOOK":"完整造型",
    "JEWELRY":"珠宝", "ACCESSORIES_VISIBLE":"配饰可见", "HANDBAG":"手袋", "SHOES_VISIBLE":"鞋履可见",
    "MATCHING_SET":"成套搭配", "SWIM_COVERUP":"泳装罩衫", "SINGLE_ITEM":"单品展示",
}


def wrap(text: str, width: int) -> list[str]:
    return [text[i:i + width] for i in range(0, len(text), width)] or [""]


def load_rows() -> list[dict]:
    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
    tops = [dict(r) for r in con.execute("""
        SELECT ia.*, i.source_url, p.title FROM image_analysis ia
        JOIN images i USING(store_id,product_id,position) JOIN products p USING(store_id,product_id)
        WHERE ia.store_id='aloruh_shein' AND i.position=1
    """)]
    pending = [dict(r) for r in con.execute("""
        SELECT p.product_id,p.title,i.position,i.source_url FROM products p JOIN images i USING(store_id,product_id)
        WHERE p.store_id='aloruh_shein' AND p.category_group='SKIRTS' AND i.position=1 ORDER BY p.product_id
    """)]
    con.close()
    unique = list({r["source_url"]: r for r in pending}.values())
    skirt_map = {f"aloruh_shein:SKIRTS:1:{i}": row for i, row in enumerate(unique, 1)}
    skirts = []
    for line in (DATA / "image_analysis_skirts_cover_aloruh_shein.jsonl").read_text(encoding="utf-8").splitlines():
        item = json.loads(line); base = skirt_map.get(item["key"])
        if base:
            skirts.append({**base, **item["analysis"], "tags_json": json.dumps(item["analysis"]["tags"], ensure_ascii=False), "group":"SKIRTS"})
    for row in tops: row["group"] = "TOPS"
    return tops + skirts


def tags(row: dict) -> dict:
    return json.loads(row["tags_json"])


def distribution(rows: list[dict], dimension: str, limit: int = 7) -> list[tuple[str, int]]:
    counts = Counter(v for r in rows for v in tags(r).get(dimension, []))
    return counts.most_common(limit)


def fetch(url: str) -> Path | None:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (hashlib.sha256(url.encode("utf-8")).hexdigest()[:20] + ".jpg")
    if path.exists(): return path
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as response: raw = response.read()
        image = Image.open(io.BytesIO(raw)).convert("RGB"); image.thumbnail((1400, 1800))
        image.save(path, quality=90); return path
    except Exception:
        return None


def image_crop(c: Canvas, path: Path, x: float, y: float, w: float, h: float) -> None:
    image = Image.open(path); scale = max(w / image.width, h / image.height)
    size = (max(1, int(w / scale)), max(1, int(h / scale)))
    left, top = (image.width - size[0]) // 2, (image.height - size[1]) // 2
    crop = image.crop((left, top, left + size[0], top + size[1]))
    buf = io.BytesIO(); crop.save(buf, "JPEG", quality=88); buf.seek(0)
    c.drawImage(ImageReader(buf), x, y, w, h, mask="auto")


class Deck:
    def __init__(self, rows: list[dict]):
        OUT.parent.mkdir(parents=True, exist_ok=True)
        pdfmetrics.registerFont(TTFont("CN", r"C:\Windows\Fonts\msyh.ttc"))
        pdfmetrics.registerFont(TTFont("CNB", r"C:\Windows\Fonts\msyhbd.ttc"))
        self.c, self.rows, self.page = Canvas(str(OUT), pagesize=PAGE), rows, 0

    def base(self, title: str, eyebrow: str = "ALORUH VISUAL DIAGNOSTIC") -> None:
        self.page += 1; c = self.c; c.setFillColor(BG); c.rect(0, 0, *PAGE, fill=1, stroke=0)
        c.setFillColor(ACCENT); c.rect(0, PAGE[1] - 0.16 * inch, PAGE[0], 0.16 * inch, fill=1, stroke=0)
        c.setFont("CN", 8); c.setFillColor(MUTED); c.drawString(0.65*inch, PAGE[1]-0.52*inch, eyebrow)
        c.setFont("CNB", 24); c.setFillColor(INK); c.drawString(0.65*inch, PAGE[1]-0.95*inch, title)
        c.setFont("CN", 8); c.setFillColor(MUTED); c.drawRightString(PAGE[0]-0.55*inch, 0.35*inch, f"{self.page:02d}")

    def text(self, x: float, y: float, text: str, size=12, color=INK, width=34, leading=1.45) -> float:
        self.c.setFont("CN", size); self.c.setFillColor(color)
        for line in wrap(text, width): self.c.drawString(x, y, line); y -= size * leading
        return y

    def bullets(self, items: list[str], x=.9*inch, y=5.6*inch, width=44) -> None:
        for item in items:
            self.c.setFillColor(ACCENT); self.c.circle(x, y+3, 3, fill=1, stroke=0)
            y = self.text(x+.22*inch, y, item, 13, INK, width) - .12*inch

    def bars(self, values: list[tuple[str,int]], total: int, x=.8*inch, y=5.55*inch, w=5.4*inch) -> None:
        top = max((n for _, n in values), default=1)
        for label, n in values:
            self.c.setFont("CN", 10); self.c.setFillColor(INK); self.c.drawString(x, y, ZH.get(label,label))
            self.c.setFillColor(HexColor("#DED4D0")); self.c.roundRect(x+1.25*inch,y-2,w,10,5,fill=1,stroke=0)
            self.c.setFillColor(ACCENT); self.c.roundRect(x+1.25*inch,y-2,w*n/top,10,5,fill=1,stroke=0)
            self.c.setFillColor(MUTED); self.c.drawRightString(x+1.15*inch,y, f"{n/total:.0%}")
            y -= .52*inch

    def photos(self, candidates: list[dict], x=7.2*inch, y=.95*inch, count=3) -> None:
        shown = 0
        step = max(1, len(candidates) // max(count * 2, 1))
        for row in candidates[::step]:
            p = fetch(row["source_url"])
            if not p: continue
            image_crop(self.c, p, x + shown*1.75*inch, y, 1.55*inch, 4.85*inch); shown += 1
            if shown == count: break

    def finish(self): self.c.save()


def candidates(rows: list[dict], dim: str, tag: str, group: str | None = None) -> list[dict]:
    return [r for r in rows if (not group or r["group"] == group) and tag in tags(r).get(dim, [])]


def build() -> None:
    rows = load_rows(); deck = Deck(rows); tops = [r for r in rows if r["group"] == "TOPS"]; skirts = [r for r in rows if r["group"] == "SKIRTS"]
    deck.base("Aloruh 店铺纯视觉诊断", "A VISUAL-FIRST STORE DIAGNOSTIC · 2026.08")
    deck.text(.72*inch, 4.8*inch, "从415张已分析首图中，提炼可复用的视觉规则、品类差异与拍摄改进方向。", 18, INK, 36)
    deck.text(.72*inch, 3.65*inch, "不使用曝光、点击、CTR、CVR、销量等经营指标", 12, ACCENT, 40)
    deck.photos(rows, 7.4*inch, .75*inch)
    deck.c.showPage()
    deck.base("Executive Summary｜执行摘要")
    deck.bullets(["Aloruh 的核心视觉资产是“女性化设计细节 + 完整造型”：领口、肩部、腰线和材质纹理共同承担商品识别。",
                  "首图高度集中于正面站姿和中近景，商品读取效率高，但动作、视角与细节层次存在同质化。",
                  "棚拍、居家、镜面与建筑空间并存，形成电商净图与社交生活方式两套语言；目前缺少稳定的系列化切换规则。",
                  "优先建立四张图拍摄系统：结构首图、动态造型、场景氛围、细节证据，并按 Tops 与 Skirts 分别控制裁切。"])
    deck.c.showPage()
    deck.base("证据范围：首图视觉，不是经营表现")
    deck.bullets([f"分析对象：Aloruh(shein) 已完成视觉分析的首图 {len(rows)} 张，其中 Tops {len(tops)} 张、Skirts {len(skirts)} 张。",
                  "结构化证据：商品类别、廓形、设计元素、穿着场景、构图、动作、卖点、拍摄场景、材质、色彩图案、视觉语言、搭配方式。",
                  "光线由现有视觉语言标签统计；模特状态与图文叠加仅在高清样本中作定性观察，未冒充全量数据。",
                  "所有比例以图片为分母；多选标签可使同一维度的比例合计超过100%。"])
    deck.c.showPage()
    deck.base("样本结构：Tops 是主证据，Skirts 提供品类校正")
    deck.bars([("TOPS",len(tops)),("SKIRTS",len(skirts))], len(rows), w=5.2*inch); deck.photos(tops[:8]+skirts[:8])
    deck.c.showPage()
    deck.base("视觉定位：精致外出感与社交化表达并行")
    deck.bullets(["品牌不是单一棚拍电商风，而是同时使用电商净图、生活方式和社交UGC语言。",
                  "女性化识别主要来自挂脖、细肩带、不对称、透视、蕾丝与装饰元素，而不是依赖文字或促销贴片。",
                  "完整造型和珠宝搭配覆盖面极高，说明“怎么穿”与“衣服是什么”同等重要。"])
    deck.photos(candidates(rows,"visual_language","LIFESTYLE")+rows)
    deck.c.showPage()
    for dim, title in DIMENSIONS:
        values = distribution(rows, dim); top = values[0][0]
        deck.base(f"{title}：{ZH.get(top,top)}构成当前主轴", "12-DIMENSION VISUAL PROFILE")
        deck.bars(values, len(rows)); deck.photos(candidates(rows,dim,top)+rows)
        deck.text(.8*inch, 1.05*inch, f"读取方式：按图片计数；该维度可多选。Top 1 为 {ZH.get(top,top)}，覆盖 {values[0][1]}/{len(rows)} 张。", 9, MUTED, 55)
        deck.c.showPage()
    deck.base("Tops 与 Skirts：构图必须按品类分流")
    deck.bullets(["Tops 需要保留领口、肩线与腰部，四分之三身和半身更适合作为结构首图。",
                  "Skirts 需要完整交代腰头、臀腿关系与下摆，优先全身或更低裁切，不能复用上衣首图模板。",
                  "两类都应补充背面、侧面和动态图，避免正面站姿成为唯一商品解释。"])
    deck.photos(tops[:6]+skirts[:10]); deck.c.showPage()
    for title, dims in [("构图 × 场景：两套语言尚未形成明确秩序",("composition","scene")),
                        ("动作 × 卖点：正面站姿承载过多任务",("view_action","selling_points")),
                        ("材质 × 光线：细节需要更稳定的证据图",("material_texture","visual_language"))]:
        deck.base(title, "MULTI-DIMENSION COMBINATION")
        left, right = distribution(rows,dims[0],5), distribution(rows,dims[1],5)
        deck.bars(left,len(rows),.75*inch,5.55*inch,3.9*inch); deck.bars(right,len(rows),6.65*inch,5.55*inch,3.9*inch)
        deck.text(.8*inch,1.2*inch,"组合建议：把一个画面任务固定为“构图 + 动作 + 卖点 + 场景”，减少一张图同时承担商品说明与氛围叙事。",11,ACCENT,70)
        deck.c.showPage()
    deck.base("首图语法：高读取效率，但变化空间不足")
    deck.bullets(["主模板：四分之三身/半身 + 正面站姿 + 领口/肩部/腰线 + 完整造型。",
                  "优势：商品轮廓与搭配关系能快速建立，适合复杂上衣。",
                  "风险：相似裁切和站姿反复出现，系列之间缺少鲜明节奏；细节、背面和动态证据不足。"])
    deck.photos(candidates(rows,"view_action","FRONT_VIEW")); deck.c.showPage()
    deck.base("一致性诊断：风格丰富，系统边界偏弱")
    deck.bullets(["保持：女性化细节、完整造型、珠宝配饰和暖调/柔光资产。",
                  "统一：同一系列的背景色、裁切高度、模特视线、配饰密度和图片顺序。",
                  "分流：棚拍用于结构说明；家居/建筑/街景用于生活方式；镜面UGC用于社交语气，三者不要随机混排。",
                  "补齐：每款至少一张无遮挡结构图和一张材质/工艺特写。"])
    deck.photos(candidates(rows,"scene","HOME")+candidates(rows,"scene","STUDIO_NEUTRAL")); deck.c.showPage()
    deck.base("高清样本观察：光线、姿态与图文叠加")
    smoke = json.loads((ROOT/"output/visual-analysis-sol-smoke/result.json").read_text(encoding="utf-8"))
    local = Path(smoke["images"][0]["path"]); image_crop(deck.c, ROOT/local, .8*inch, .75*inch, 4.2*inch, 5.1*inch)
    deck.bullets(["光线：侧向硬光能强化皮革/光泽质感，但深色肩颈与背景容易粘连。",
                  "模特状态：正面静态利于结构读取；动态姿态应服务袖量、下摆或背部，而不是只增加情绪。",
                  "图文叠加：当前样本依赖画面本身而非文字贴片，建议继续保持低信息干扰。"],5.5*inch,5.45*inch,35)
    deck.c.showPage()
    deck.base("竞品参照：不是复制风格，而是拆解任务分工")
    for i, item in enumerate(smoke["images"]):
        p = ROOT / item["path"]; image_crop(deck.c,p,.65*inch+i*2.5*inch,1.25*inch,2.12*inch,4.35*inch)
        deck.text(.65*inch+i*2.5*inch,.98*inch,item["store_id"].replace("_"," "),9,MUTED,20)
    deck.c.showPage()
    deck.base("推荐四张图系统：每张只承担一个核心任务")
    deck.bullets(["01 结构首图：正面、无遮挡、统一裁切，明确领口/腰线/下摆。",
                  "02 动态造型：用走动、转身、抬臂展示垂坠、袖量与裙摆。",
                  "03 场景氛围：为约会、度假、派对建立可复用场景模板。",
                  "04 细节证据：材质、装饰、闭合、背部与工艺的近景说明。"])
    deck.photos(rows[::17]); deck.c.showPage()
    deck.base("Tops 拍摄规范：优先领口、肩线与腰部结构")
    deck.bullets(["首图裁切保持头部至胯部，避免头发遮住肩线或领口。","至少一张45度侧面和一张背面，解释露背、系带及束身结构。",
                  "珠宝从“默认叠加”改为按款式控制：结构复杂时降低配饰密度。","透明、蕾丝、亮片类补充同色背景分离和材质微距。"])
    deck.photos(tops[::21]); deck.c.showPage()
    deck.base("Skirts 拍摄规范：完整交代腰头、腿部与下摆")
    deck.bullets(["首图至少覆盖腰部至脚部；短裙也要保留下摆和腿部比例。","动态页使用迈步、转身或轻提裙摆，展示垂坠和摆量。",
                  "上装与配饰不应抢走裙装主体；控制上半身视觉复杂度。","补充侧面、背面与腰头近景，避免只展示正面造型。"])
    deck.photos(skirts[::5]); deck.c.showPage()
    deck.base("实施优先级：先统一首图，再扩展叙事")
    deck.bullets(["P0｜定义 Tops、Skirts 两套首图裁切和无遮挡标准。","P0｜按系列固定背景、光线、配饰密度和图片顺序。",
                  "P1｜建立四张图任务模板，并为每款标记缺失任务。","P1｜把光线、模特状态、图文叠加纳入下一轮结构化分析。",
                  "P2｜用视觉一致性、模板覆盖率、主体突出度评估执行质量。"])
    deck.c.showPage()
    deck.base("无需经营指标，也能持续检查视觉执行")
    deck.bullets(["模板覆盖率：每款是否具备结构、动态、场景、细节四类图片。","系列一致性：同系列背景、光线、裁切、配饰是否遵守统一规则。",
                  "主体突出度：商品是否被头发、手臂、配饰或背景干扰。","结构完整度：领口、腰线、下摆、背面、闭合与材质是否被充分解释。"])
    deck.c.showPage()
    deck.base("Further Questions｜下一轮需要回答")
    deck.bullets(["不同系列应保留几套稳定场景模板，才能兼顾识别度与丰富度？","哪些款式必须降低珠宝和手袋密度，才能让结构成为第一视觉层级？",
                  "镜面UGC应作为固定图片序列中的哪一位，而不是随机出现？","新增光线、模特状态、图文叠加全量标签后，哪些组合最能代表品牌？"])
    deck.c.showPage()
    deck.base("Caveats｜边界与假设")
    deck.bullets(["本报告只分析当前已完成标签的415张首图，不代表店铺所有历史素材。","图片分析标签为视觉模型结果，适合发现结构性规律，不替代逐款人工审片。",
                  "Skirts 证据量小于 Tops，品类对比用于校正拍摄规则，不用于判断商业表现。","报告不使用也不推断曝光、点击、转化、销量或ROI。"])
    deck.c.showPage()
    deck.base("结论：把丰富视觉资产变成可重复的系统")
    deck.text(.85*inch,4.8*inch,"Aloruh 已经拥有清晰的女性化细节、完整造型与生活方式语言。下一步不是增加更多随机风格，而是让每张图承担明确任务，让 Tops 与 Skirts 使用不同的结构模板，并用统一光线、裁切和图片顺序形成系列识别。",18,INK,48)
    deck.text(.85*inch,2.1*inch,"建议下一步：按本报告规则选择一个 Tops 系列和一个 Skirts 系列，制作可直接执行的拍摄样板。",13,ACCENT,58)
    deck.finish()
    NOTES.write_text(json.dumps({"generated":"2026-08-20","rows":len(rows),"tops":len(tops),"skirts":len(skirts),"sources":[str(DB),str(DATA/"image_analysis_skirts_cover_aloruh_shein.jsonl"),str(ROOT/"output/visual-analysis-sol-smoke/result.json")],"omitted_metrics":["曝光","点击","CTR","CVR","销量","ROI"],"chart_contract":"Horizontal ranked bars; image denominator; multi-label shares may exceed 100%; zero-based bars; burgundy single-root palette."},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


if __name__ == "__main__": build()
