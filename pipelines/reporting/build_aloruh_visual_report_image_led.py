from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas


ROOT = Path(__file__).resolve().parents[2]
BASE_PATH = Path(__file__).with_name("build_aloruh_visual_report.py")
SPEC = importlib.util.spec_from_file_location("base_report", BASE_PATH)
B = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(B)
OUT = ROOT / "output/pdf/Aloruh纯视觉诊断-图片结论版.pdf"
NOTES = ROOT / "output/pdf/Aloruh纯视觉诊断-图片结论版-source-notes.json"
W, H = B.PAGE
BLACK, WHITE, GREY = HexColor("#111111"), HexColor("#FFFFFF"), HexColor("#707070")
WARM, WINE, LINE = HexColor("#F4F0EB"), HexColor("#78233C"), HexColor("#D8D2CC")


def load_competitors() -> dict[str, list[dict]]:
    con = sqlite3.connect(B.DB); con.row_factory = sqlite3.Row
    result = {}
    for store in ("princess_polly", "motel", "prettylittlething"):
        rows = [dict(r) for r in con.execute("""
            SELECT ia.*,i.source_url,p.title,p.category_group FROM image_analysis ia
            JOIN images i USING(store_id,product_id,position) JOIN products p USING(store_id,product_id)
            WHERE ia.store_id=? AND i.position=1 AND p.category_group IN ('TOPS','SKIRTS')
            ORDER BY p.catalog_rank LIMIT 500
        """, (store,))]
        result[store] = rows
    con.close(); return result


def choose(rows: list[dict], dim: str | None = None, tag: str | None = None, count: int = 12) -> list[dict]:
    pool = [r for r in rows if not dim or tag in B.tags(r).get(dim, [])]
    if not pool: pool = rows
    step = max(1, len(pool) // count)
    return pool[::step][:count]


def pct(rows: list[dict], dim: str, tag: str) -> int:
    return round(100 * sum(tag in B.tags(r).get(dim, []) for r in rows) / max(len(rows), 1))


class VisualDeck:
    def __init__(self, rows: list[dict]):
        OUT.parent.mkdir(parents=True, exist_ok=True)
        pdfmetrics.registerFont(TTFont("CN", r"C:\Windows\Fonts\msyh.ttc"))
        pdfmetrics.registerFont(TTFont("CNB", r"C:\Windows\Fonts\msyhbd.ttc"))
        self.c, self.rows, self.n = Canvas(str(OUT), pagesize=B.PAGE), rows, 0

    def new(self, title: str, kicker="ALORUH VISUAL AUDIT", dark=False, subtitle=""):
        self.n += 1; c = self.c; bg = BLACK if dark else WHITE; ink = WHITE if dark else BLACK
        c.setFillColor(bg); c.rect(0, 0, W, H, fill=1, stroke=0)
        c.setFillColor(ink); c.setFont("CN", 7); c.drawString(.42*inch, H-.35*inch, kicker)
        c.setFont("CNB", 23); c.drawString(.42*inch, H-.78*inch, title)
        if subtitle:
            c.setFont("CN", 9); c.setFillColor(HexColor("#C8C8C8") if dark else GREY)
            c.drawString(.43*inch, H-1.04*inch, subtitle)
        c.setFont("CN", 7); c.drawRightString(W-.36*inch, .25*inch, f"{self.n:02d}")

    def end(self): self.c.showPage()

    def text(self, x, y, text, size=12, color=BLACK, width=38, bold=False, leading=1.35):
        self.c.setFont("CNB" if bold else "CN", size); self.c.setFillColor(color)
        for line in B.wrap(text, width): self.c.drawString(x, y, line); y -= size*leading
        return y

    def image(self, row, x, y, w, h):
        path = B.fetch(row["source_url"])
        if path: B.image_crop(self.c, path, x, y, w, h)

    def grid(self, rows, x=.42*inch, y=.5*inch, w=12.48*inch, h=5.65*inch, cols=6, gap=.08*inch):
        selected = choose(rows, count=cols*2); cell_w=(w-gap*(cols-1))/cols; cell_h=(h-gap)/2
        for i,row in enumerate(selected):
            self.image(row,x+(i%cols)*(cell_w+gap),y+(1-i//cols)*(cell_h+gap),cell_w,cell_h)

    def caption(self, text, x=.48*inch, y=.48*inch, width=58, dark=False):
        color = WHITE if dark else BLACK
        self.c.setFillColor(HexColor("#000000") if dark else HexColor("#FFFFFF")); self.c.setFillAlpha(.82)
        self.c.roundRect(x-.12*inch,y-.12*inch,6.6*inch,.62*inch,.08*inch,fill=1,stroke=0); self.c.setFillAlpha(1)
        self.text(x,y,text,10,color,width,bold=True)

    def section(self, en, zh, row, line):
        self.n += 1; self.image(row,0,0,W,H); self.c.setFillColor(BLACK); self.c.setFillAlpha(.6)
        self.c.rect(0,0,W,H,fill=1,stroke=0); self.c.setFillAlpha(1); self.c.setFillColor(WHITE)
        self.c.setFont("CNB",32); self.c.drawString(.7*inch,4.15*inch,en)
        self.c.setFont("CNB",22); self.c.drawString(.72*inch,3.65*inch,zh)
        self.text(.72*inch,2.9*inch,line,12,WHITE,54); self.c.setFont("CN",7)
        self.c.drawRightString(W-.36*inch,.25*inch,f"{self.n:02d}"); self.end()

    def statement(self, title, body, row, dark=True):
        self.new(title,dark=dark); self.image(row,0,0,W,H); self.c.setFillColor(BLACK); self.c.setFillAlpha(.52)
        self.c.rect(0,0,W,H,fill=1,stroke=0); self.c.setFillAlpha(1)
        self.text(.72*inch,3.2*inch,body,18,WHITE,45,bold=True,leading=1.5); self.end()

    def finish(self): self.c.save()


def build() -> None:
    rows=B.load_rows(); tops=[r for r in rows if r["group"]=="TOPS"]; skirts=[r for r in rows if r["group"]=="SKIRTS"]
    comp=load_competitors(); d=VisualDeck(rows)
    # Cover and answer-first opening
    d.new("ALORUH", "STORE VISUAL DIAGNOSTIC · IMAGE-LED EDITION", dark=True, subtitle="店铺纯视觉诊断｜图片与结论版")
    cover=choose(rows,count=5)
    for i,r in enumerate(cover): d.image(r,i*W/5,0,W/5,H-1.28*inch)
    d.text(.52*inch,.48*inch,"从415张首图中提炼品牌视觉代码、首图语法与拍摄升级方向",13,WHITE,48,bold=True); d.end()
    d.new("Executive Summary｜执行摘要", subtitle="先给结论，再进入图片证据")
    cards=[("01","品牌资产","女性化细节、完整造型与社交化场景已形成鲜明基础。"),
           ("02","主要问题","正面站姿与中近景承担过多任务，系列节奏和细节证据不足。"),
           ("03","升级方向","从“展示单品”转向“结构图、动态图、场景图、细节图”四类分工。"),
           ("04","品类分流","Tops 强调领口肩线与腰部；Skirts 必须完整交代腰头、腿部和下摆。")]
    for i,(num,title,body) in enumerate(cards):
        x=.55*inch+i*3.15*inch; d.c.setFillColor(WARM); d.c.roundRect(x,.75*inch,2.75*inch,4.95*inch,.08*inch,fill=1,stroke=0)
        d.c.setFillColor(WINE); d.c.setFont("CNB",32); d.c.drawString(x+.18*inch,5.1*inch,num)
        d.text(x+.18*inch,4.35*inch,title,15,BLACK,12,bold=True); d.text(x+.18*inch,3.75*inch,body,11,GREY,15)
    d.end()
    d.new("视觉样本范围", subtitle="Aloruh(shein) 首图：Tops 343张 / Skirts 72张")
    d.grid(rows,cols=8); d.caption("所有结论仅基于图片、视觉标签与高清样本观察；不使用任何经营数据。",width=54); d.end()
    d.section("STORE VISUAL AUDIT","店铺视觉分析",rows[24],"先识别稳定视觉资产，再判断哪些表达需要统一、分流与补齐。")
    # Store profile
    d.new("女性化细节 + 完整造型，是当前最稳定的视觉资产")
    d.grid(rows,cols=7); d.caption("挂脖、细肩带、不对称、蕾丝、透视与珠宝搭配反复出现，品牌识别主要由服装细节和造型共同完成。",width=66); d.end()
    d.new("首图不是纯棚拍体系，而是三种语言并存")
    scene_groups=[("中性棚拍","STUDIO_NEUTRAL"),("室内 / 镜面","HOME"),("生活方式","ARCHITECTURE")]
    for i,(label,tag) in enumerate(scene_groups):
        x=.45*inch+i*4.2*inch; pool=choose(rows,"scene",tag,6)
        for j,r in enumerate(pool[:6]): d.image(r,x+(j%3)*1.3*inch,.8*inch+(1-j//3)*2.35*inch,1.18*inch,2.2*inch)
        d.text(x,5.75*inch,label,12,BLACK,16,bold=True)
    d.end()
    d.new("视觉语气：电商净图与社交生活方式平行")
    left=choose(rows,"visual_language","ECOMMERCE_CLEAN",8); right=choose(rows,"visual_language","SOCIAL_UGC",8)
    for i,r in enumerate(left): d.image(r,.45*inch+(i%4)*1.45*inch,.75*inch+(1-i//4)*2.45*inch,1.33*inch,2.3*inch)
    for i,r in enumerate(right): d.image(r,7.05*inch+(i%4)*1.45*inch,.75*inch+(1-i//4)*2.45*inch,1.33*inch,2.3*inch)
    d.text(.45*inch,5.75*inch,"电商净图｜结构读取",11,BLACK,22,bold=True); d.text(7.05*inch,5.75*inch,"社交UGC｜氛围与亲近感",11,BLACK,24,bold=True); d.end()
    d.statement("核心判断","视觉元素并不缺，真正缺的是：同一系列中，背景、光线、裁切与图片顺序的稳定规则。",rows[87])
    # First image types
    d.section("FIRST IMAGE TYPES","首图类型",rows[112],"首图应先解决商品结构，再由后续图片承担动作、场景和细节。")
    for tag,title,conclusion in [("THREE_QUARTER","四分之三身是主模板",f"覆盖约{pct(rows,'composition',tag)}%，能同时交代上衣结构与完整造型。"),
                                 ("HALF_BODY","半身图强化领口与腰线",f"覆盖约{pct(rows,'composition',tag)}%，适合复杂领口、肩部与束身结构。"),
                                 ("FULL_BODY","全身图供给明显不足",f"仅约{pct(rows,'composition',tag)}%，Skirts 与完整比例展示需要更多全身画面。")]:
        d.new(title,subtitle=conclusion); d.grid(choose(rows,"composition",tag,12),cols=6); d.end()
    d.new("正面站姿承担了过多解释任务")
    d.grid(choose(rows,"view_action","FRONT_VIEW",14),cols=7)
    d.caption(f"正面约{pct(rows,'view_action','FRONT_VIEW')}%，站姿约{pct(rows,'view_action','STANDING')}%；结构清楚，但动作与视角层次容易趋同。",width=64); d.end()
    d.new("需要补足的视角：侧面、背面、动态和细节")
    missing=choose(rows,"view_action","SIDE_VIEW",4)+choose(rows,"view_action","BACK_VIEW",4)+choose(rows,"view_action","SITTING",4)
    d.grid(missing,cols=6); d.caption("这些画面不应随机出现，而应分别解释侧缝、露背、系带、垂坠、袖量和裙摆。",width=62); d.end()
    # Detail codes
    d.section("GARMENT DETAILS","服装细节与卖点",rows[145],"视觉识别来自设计结构；图片必须让关键部位无遮挡、可比较、可复用。")
    detail_pages=[("领口与肩部是第一视觉焦点","selling_points","NECKLINE","挂脖、细肩带和不对称领口需要控制头发与珠宝遮挡。"),
                  ("腰线承担廓形解释","selling_points","WAIST","束身、抽褶与贴合关系必须保留腰部完整轮廓。"),
                  ("蕾丝、网纱与雪纺需要近景证据","material_texture","LACE","同色面料容易丢失纹理，需通过侧光和细节图建立层次。"),
                  ("纯色为主，颜色依赖材质和造型建立差异","color_pattern","PATTERN_SOLID","黑、白、棕占据主轴；色彩不是唯一识别点，结构与面料更重要。")]
    for title,dim,tag,cap in detail_pages:
        d.new(title); d.grid(choose(rows,dim,tag,12),cols=6); d.caption(cap,width=63); d.end()
    # Scenes, styling and formulas
    d.section("VISUAL CODES","构图、场景与搭配代码",rows[201],"把每张图固定为“构图-动作-卖点-场景”，避免一张图同时承担全部任务。")
    code_pages=[("棚拍结构图","scene","STUDIO_NEUTRAL","四分之三身 / 正面站姿 / 领口腰线 / 中性棚拍"),
                ("室内生活方式","scene","HOME","半身或全身 / 自然动作 / 完整造型 / 居家空间"),
                ("镜面社交语气","scene","MIRROR","镜面自拍 / 视线移开 / 搭配关系 / 低干扰背景"),
                ("建筑与街景","scene","ARCHITECTURE","全身或动态 / 场景互动 / 轮廓比例 / 建筑空间"),
                ("珠宝与手袋不能默认叠加","styling","JEWELRY","结构复杂时减配；造型图再增加珠宝、手袋与鞋履。")]
    for title,dim,tag,formula in code_pages:
        d.new(title,subtitle=formula); d.grid(choose(rows,dim,tag,12),cols=6); d.end()
    d.new("三套固定图片公式")
    formulas=[("STRUCTURE","四分之三身","正面站姿","领口 / 腰线","中性棚拍"),
              ("MOTION","全身","走动 / 转身","垂坠 / 裙摆","建筑 / 街景"),
              ("DETAIL","近景","静态无遮挡","材质 / 工艺","纯净背景")]
    for i,row in enumerate(formulas):
        x=.62*inch+i*4.18*inch; d.c.setFillColor(WARM); d.c.rect(x,.8*inch,3.72*inch,4.95*inch,fill=1,stroke=0)
        d.text(x+.22*inch,5.12*inch,row[0],20,WINE,18,bold=True)
        for j,value in enumerate(row[1:]): d.text(x+.22*inch,4.2*inch-j*.7*inch,value,12,BLACK,20,bold=j==0)
    d.end()
    # Competitor codes
    d.section("BRAND VISUAL CODES","跨店视觉代码",comp["princess_polly"][12],"竞品用于拆解视觉任务，不用于复制品牌风格。")
    profiles=[("ALORUH",rows,"细节密集 / 完整造型 / 场景混合"),("PRINCESS POLLY",comp["princess_polly"],"明亮生活方式 / 轻松动作 / 系列化背景"),
              ("MOTEL",comp["motel"],"编辑感 / 复古色彩 / 强姿态"),("PRETTY LITTLE THING",comp["prettylittlething"],"高密度造型 / 强对比 / 直接商品展示")]
    for name,pool,code in profiles:
        d.new(name,subtitle=code); d.grid(pool,cols=7); d.end()
    d.new("Aloruh 的差异点：细节最丰富，但系列边界需要更清楚")
    for i,(name,pool,code) in enumerate(profiles):
        x=.45*inch+i*3.15*inch; d.image(choose(pool,count=4)[i%4],x,.95*inch,2.82*inch,4.75*inch)
        d.text(x,5.92*inch,name,10,BLACK,20,bold=True); d.text(x, .66*inch,code,8,GREY,18)
    d.end()
    # Upgrade direction
    d.section("VISUAL UPGRADE DIRECTION","视觉升级方向",rows[250],"不是增加更多随机风格，而是让每张图片的任务更明确、系列更可识别。")
    d.new("四套系列方向：用场景和光线建立记忆点")
    series=[("CASUAL OUTING","休闲外出","STREET"),("ROMANTIC DATE","浪漫约会","HOME"),("VACATION SUN-KISSED","阳光度假","BEACH"),("PARTY NIGHT OUT","派对夜出","PARTY")]
    for i,(en,zh,tag) in enumerate(series):
        x=.35*inch+i*3.22*inch; pool=choose(rows,"scene",tag,4); d.image(pool[0],x,.85*inch,2.95*inch,4.95*inch)
        d.c.setFillColor(BLACK); d.c.setFillAlpha(.45); d.c.rect(x,.85*inch,2.95*inch,1.05*inch,fill=1,stroke=0); d.c.setFillAlpha(1)
        d.text(x+.14*inch,1.48*inch,en,11,WHITE,24,bold=True); d.text(x+.14*inch,1.15*inch,zh,9,WHITE,20)
    d.end()
    d.new("四张图拍摄系统：一张图只承担一个核心任务")
    tasks=[("01","结构首图","无遮挡，交代领口、腰线和下摆"),("02","动态造型","动作服务袖量、垂坠或裙摆"),
           ("03","场景氛围","场景与穿着情境保持一致"),("04","细节证据","材质、装饰、闭合和背部近景")]
    for i,(num,name,desc) in enumerate(tasks):
        x=.5*inch+i*3.13*inch; d.c.setFillColor(WARM); d.c.rect(x,.9*inch,2.8*inch,4.75*inch,fill=1,stroke=0)
        d.text(x+.18*inch,5.0*inch,num,30,WINE,10,bold=True); d.text(x+.18*inch,4.15*inch,name,14,BLACK,14,bold=True); d.text(x+.18*inch,3.48*inch,desc,10,GREY,15)
    d.end()
    d.new("Tops：首图优先领口、肩线与腰部结构")
    d.grid(tops,cols=7); d.caption("头发与珠宝不得遮挡关键结构；补侧面、背面和材质近景。",width=58); d.end()
    d.new("Skirts：必须完整交代腰头、腿部与下摆")
    d.grid(skirts,cols=7); d.caption("首图降低裁切；动态页展示摆量；上装与配饰不能抢走裙装主体。",width=60); d.end()
    d.new("执行顺序：先统一，再扩展")
    steps=[("PHASE 01","统一首图","Tops / Skirts 两套裁切标准"),("PHASE 02","统一系列","背景、光线、配饰密度、图片顺序"),
           ("PHASE 03","补齐任务","结构、动态、场景、细节四类图片"),("PHASE 04","持续审片","一致性、主体突出度、结构完整度")]
    for i,(phase,title,body) in enumerate(steps):
        y=5.45*inch-i*1.22*inch; d.text(.72*inch,y,phase,10,WINE,14,bold=True); d.text(2.25*inch,y,title,14,BLACK,12,bold=True); d.text(4.15*inch,y,body,11,GREY,42)
        d.c.setStrokeColor(LINE); d.c.line(.72*inch,y-.45*inch,12.5*inch,y-.45*inch)
    d.end()
    d.new("Caveats｜边界",subtitle="图片结论版")
    d.grid(rows[::31],cols=7)
    d.caption("本报告覆盖415张已分析首图。模特状态与图文叠加仍属于高清样本观察，未作为全量比例；所有建议均为视觉执行建议。",width=72); d.end()
    d.statement("结论","Aloruh 不需要再增加更多随机风格。下一步是把女性化细节和完整造型沉淀成稳定的首图语法、系列场景和四张图拍摄系统。",rows[301])
    d.finish()
    NOTES.write_text(json.dumps({"generated":"2026-08-20","pages":d.n,"aloruh_images":len(rows),"tops":len(tops),"skirts":len(skirts),"reference_style":"image-led diagnostic; large photo grids; concise evidence-backed conclusions","excluded_topics":["exposure","clicks","CTR","CVR","sales","ROI"],"sources":[str(B.DB),str(B.DATA/"image_analysis_skirts_cover_aloruh_shein.jsonl"),str(ROOT/"output/visual-analysis-sol-smoke/result.json")],"chart_map":"No trend or performance charts. Only image counts and tag coverage shown as concise context."},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


if __name__ == "__main__": build()
