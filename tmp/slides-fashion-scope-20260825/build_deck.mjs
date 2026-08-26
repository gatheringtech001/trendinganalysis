import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const TMP = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(TMP, "..", "..");
const ASSETS = path.join(TMP, "assets");
const RENDERS = path.join(TMP, "renders-v8");
const FINAL = path.join(ROOT, "output", "Fashion-Scope-技术架构与产品体验-20260826-v8.pptx");

const W = 1280;
const H = 720;
const M = 48;
const INK = "#111111";
const MUTED = "#62666D";
const PANEL = "#F0F0F0";
const RULE = "#BEC2C8";
const BLUE = "#3D8DFF";
const LIGHT_BLUE = "#D9F0FB";
const WHITE = "#FFFFFF";
const BLACK = "#000000";
const FONT = "Microsoft YaHei";
const FONT_LATIN = "Arial";

const sources = {
  repo: ".",
  production: "https://regardsjob.eastasia.cloudapp.azure.com/fashion-scope/",
};

async function bytes(name) {
  const b = await fs.readFile(path.join(ASSETS, name));
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
}

async function writeBlob(file, blob) {
  await fs.writeFile(file, new Uint8Array(await blob.arrayBuffer()));
}

function addText(slide, text, position, style = {}, name = "text") {
  const shape = slide.shapes.add({
    geometry: "textbox",
    name,
    position,
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    fontSize: style.fontSize ?? 24,
    typeface: style.typeface ?? FONT,
    color: style.color ?? INK,
    bold: style.bold ?? false,
    alignment: style.alignment ?? "left",
    verticalAlignment: style.verticalAlignment ?? "top",
    autoFit: style.autoFit ?? "shrinkText",
    insets: style.insets ?? { top: 0, right: 0, bottom: 0, left: 0 },
  };
  return shape;
}

function addBox(slide, position, fill = PANEL, line = "none", radius = 0, name = "box") {
  return slide.shapes.add({
    geometry: radius ? "roundRect" : "rect",
    name,
    position,
    fill,
    line: line === "none"
      ? { style: "solid", fill: "none", width: 0 }
      : { style: "solid", fill: line, width: 1 },
    ...(radius ? { borderRadius: radius } : {}),
  });
}

function addRule(slide, left, top, width, color = RULE, height = 1) {
  return addBox(slide, { left, top, width, height }, color, "none", 0, "rule");
}

async function addImage(slide, name, position, options = {}) {
  const ext = path.extname(name).toLowerCase();
  return slide.images.add({
    blob: await bytes(name),
    contentType: ext === ".png" ? "image/png" : "image/jpeg",
    alt: options.alt ?? name,
    fit: options.fit ?? "cover",
    position,
    geometry: options.radius ? "roundRect" : "rect",
    ...(options.radius ? { borderRadius: options.radius } : {}),
    ...(options.crop ? { crop: options.crop } : {}),
  });
}

function addHeader(slide, title, eyebrow, page, subtitle = "") {
  addText(slide, eyebrow.toUpperCase(), { left: M, top: 28, width: 500, height: 18 },
    { fontSize: 12, typeface: FONT_LATIN, bold: true, color: BLUE }, "eyebrow");
  addText(slide, title, { left: M, top: 55, width: 1135, height: 56 },
    { fontSize: 38, bold: true }, "slide-title");
  if (subtitle) {
    addText(slide, subtitle, { left: M, top: 110, width: 1090, height: 34 },
      { fontSize: 17, color: MUTED }, "slide-subtitle");
  }
  addText(slide, String(page).padStart(2, "0"), { left: 1185, top: 34, width: 48, height: 22 },
    { fontSize: 13, typeface: FONT_LATIN, color: MUTED, alignment: "right" }, "page-number");
}

function addFooter(slide, text = "Fashion Scope · repository + production evidence") {
  addRule(slide, M, 684, 1184, "#D7D9DD");
  addText(slide, text, { left: M, top: 691, width: 1120, height: 16 },
    { fontSize: 10, color: MUTED }, "footer");
}

function addNotes(slide, lines) {
  slide.speakerNotes.textFrame.setText(`[Sources]\n${lines.map((line) => `- ${line}`).join("\n")}\n[/Sources]`);
  slide.speakerNotes.setVisible(true);
}

function metric(slide, value, label, left, top, width, accent = false) {
  addText(slide, value, { left, top, width, height: 76 },
    { fontSize: 48, typeface: FONT_LATIN, bold: true, color: accent ? BLUE : INK }, `metric-${label}`);
  addText(slide, label, { left, top: top + 66, width, height: 42 },
    { fontSize: 16, color: MUTED }, `metric-label-${label}`);
}

function flowNode(slide, options) {
  const { position, step, title, detail, accent = false, dark = false } = options;
  const fill = dark ? BLACK : accent ? LIGHT_BLUE : PANEL;
  const titleColor = dark ? WHITE : INK;
  const detailColor = dark ? "#D7D7D7" : MUTED;
  addBox(slide, position, fill, "none", 8, `flow-${step}`);
  addText(slide, step, {
    left: position.left + 18, top: position.top + 16, width: 50, height: 24,
  }, { fontSize: 16, typeface: FONT_LATIN, bold: true, color: accent ? BLUE : detailColor });
  addText(slide, title, {
    left: position.left + 18, top: position.top + 48, width: position.width - 36, height: 42,
  }, { fontSize: 20, bold: true, color: titleColor });
  if (detail) {
    addText(slide, detail, {
      left: position.left + 18, top: position.top + 92, width: position.width - 36,
      height: position.height - 104,
    }, { fontSize: 16, color: detailColor });
  }
}

function flowArrow(slide, options) {
  const { text = "→", position, color = BLUE } = options;
  addText(slide, text, position,
    { fontSize: 30, typeface: FONT_LATIN, bold: true, color, alignment: "center", verticalAlignment: "middle" },
    "flow-arrow");
}

function addDimensionEntry(slide, options) {
  const { left, top, width, index, title, tags, note } = options;
  addText(slide, index, { left, top: top + 2, width: 42, height: 24 },
    { fontSize: 14, typeface: FONT_LATIN, bold: true, color: BLUE }, `dimension-index-${index}`);
  addText(slide, title, { left: left + 48, top, width: width - 48, height: 30 },
    { fontSize: 20, bold: true }, `dimension-title-${index}`);
  addText(slide, tags, { left: left + 48, top: top + 36, width: width - 48, height: 42 },
    { fontSize: 16, typeface: FONT_LATIN, bold: true, color: BLUE }, `dimension-tags-${index}`);
  addText(slide, note, { left: left + 48, top: top + 78, width: width - 48, height: 30 },
    { fontSize: 16, color: MUTED }, `dimension-note-${index}`);
  addRule(slide, left, top + 112, width, "#D7D9DD");
}

function addPromptBlock(slide, position, title, body, accent = false) {
  addBox(slide, position, accent ? LIGHT_BLUE : PANEL, "none", 8, `prompt-${title}`);
  addText(slide, title, {
    left: position.left + 20, top: position.top + 18, width: position.width - 40, height: 28,
  }, { fontSize: 19, bold: true, color: accent ? BLUE : INK });
  addText(slide, body, {
    left: position.left + 20, top: position.top + 58, width: position.width - 40,
    height: position.height - 76,
  }, { fontSize: 16, color: accent ? INK : MUTED });
}

function addCodeBlock(slide, position, title, lines, accent = false) {
  addBox(slide, position, accent ? LIGHT_BLUE : PANEL, "none", 8, `code-${title}`);
  addText(slide, title, {
    left: position.left + 20, top: position.top + 18, width: position.width - 40, height: 28,
  }, { fontSize: 18, bold: true, color: accent ? BLUE : INK }, `code-title-${title}`);
  addText(slide, lines.join("\n"), {
    left: position.left + 20, top: position.top + 58, width: position.width - 40,
    height: position.height - 76,
  }, { fontSize: 16, typeface: FONT_LATIN, color: accent ? INK : MUTED }, `code-body-${title}`);
}

async function addDemoSlide(options) {
  const { title, eyebrow, page, subtitle, imageName, step, summary, details } = options;
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, title, eyebrow, page, subtitle);
  addBox(s, { left: 48, top: 158, width: 900, height: 506 }, "#F5F6F8", "#D7D9DD", 8, "demo-frame");
  await addImage(s, imageName, { left: 58, top: 168, width: 880, height: 486 },
    { alt: title, fit: "cover", radius: 6 });
  addBox(s, { left: 970, top: 158, width: 262, height: 506 }, LIGHT_BLUE, "none", 8, "demo-guide");
  addText(s, step, { left: 994, top: 186, width: 214, height: 24 },
    { fontSize: 14, typeface: FONT_LATIN, bold: true, color: BLUE }, "demo-step");
  addText(s, summary, { left: 994, top: 226, width: 214, height: 98 },
    { fontSize: 24, bold: true }, "demo-summary");
  addRule(s, 994, 342, 214, "#AFCFE1", 2);
  details.forEach((detail, index) => {
    const y = 372 + index * 82;
    addText(s, `0${index + 1}`, { left: 994, top: y, width: 30, height: 24 },
      { fontSize: 13, typeface: FONT_LATIN, bold: true, color: BLUE }, `demo-detail-index-${index}`);
    addText(s, detail, { left: 1032, top: y - 2, width: 176, height: 58 },
      { fontSize: 16, color: INK }, `demo-detail-${index}`);
  });
  addFooter(s, "Fashion Scope · production screenshot walkthrough · 2026-08-26");
  addNotes(s, [sources.production, `tmp/slides-fashion-scope-20260825/assets/${imageName}`]);
}

const p = Presentation.create({ slideSize: { width: W, height: H } });

// 1. Cover — final-delivery proof rather than a generic website screenshot.
{
  const s = p.slides.add();
  s.background.fill = BLACK;
  addText(s, "FASHION SCOPE", { left: 58, top: 58, width: 360, height: 24 },
    { fontSize: 14, typeface: FONT_LATIN, bold: true, color: "#8FD4F2" });
  addText(s, "商铺视觉数据\n如何变成可交付结论", { left: 58, top: 152, width: 480, height: 180 },
    { fontSize: 50, bold: true, color: WHITE });
  addText(s, "外部数据源 → 15维标准化 → 两种分析工作流 → 53页PDF",
    { left: 58, top: 378, width: 480, height: 88 }, { fontSize: 21, color: "#D7D7D7" });
  addRule(s, 58, 532, 440, "#343434", 2);
  addText(s, "COLLECT  /  STANDARDIZE  /  ANALYZE  /  DELIVER",
    { left: 58, top: 556, width: 470, height: 30 },
    { fontSize: 15, typeface: FONT_LATIN, bold: true, color: "#8FD4F2" });
  addText(s, "Discussion deck · 2026.08.26", { left: 58, top: 636, width: 350, height: 22 },
    { fontSize: 13, typeface: FONT_LATIN, color: "#8D9198" });
  addText(s, "FINAL DELIVERY / PAGE 53", { left: 600, top: 62, width: 320, height: 20 },
    { fontSize: 13, typeface: FONT_LATIN, bold: true, color: "#8D9198" });
  addBox(s, { left: 586, top: 96, width: 646, height: 548 }, "#1E1E1E", "none", 8);
  await addImage(s, "page-53.jpg", { left: 606, top: 118, width: 606, height: 503 },
    { alt: "Final visual diagnosis recommendation page", fit: "contain" });
  addNotes(s, [`${sources.repo}/tmp/pdfs/semantic-pages-22a1362/page-53.jpg`]);
}

let pageNumber = 2;

// Architecture diagram.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "架构核心是“批量数据底座＋按需视觉推理”", "Technical architecture", pageNumber++,
    "高频浏览与筛选由本地数据层承担；只有需要语义判断时才调用视觉模型。");
  const xs = [48, 348, 648, 948];
  const titles = ["外部数据源", "标准化数据层", "分析与证据引擎", "产品与交付"];
  const bodies = [
    "Shopify /products.json\nAlgolia browse\nWooCommerce Store API\nBrowser Use＋人工验证",
    "统一商品/图片 JSONL\n稳定商品与图片键\nURL/内容哈希去重\n15维标签＋SQLite",
    "体验1：组合筛选＋精读\n体验2：整体分析＋报告\nTerra批量打标 / Sol精读\n报告共享高清缓存与证据",
    "React 19 + Vite\nPython HTTP API\n五个Section逐章审核\nReportLab/Pillow 53页PDF",
  ];
  // Arrows are created before nodes so they stay behind the diagram entities.
  for (let i = 0; i < 3; i += 1) {
    addText(s, "→", { left: xs[i] + 250, top: 330, width: 54, height: 54 },
      { fontSize: 38, typeface: FONT_LATIN, color: BLUE, alignment: "center" }, `arrow-${i}`);
  }
  for (let i = 0; i < 4; i += 1) {
    addBox(s, { left: xs[i], top: 190, width: 252, height: 360 }, i === 2 ? LIGHT_BLUE : PANEL, "none", 8, `stage-${i}`);
    addText(s, `0${i + 1}`, { left: xs[i] + 22, top: 216, width: 70, height: 34 },
      { fontSize: 18, typeface: FONT_LATIN, bold: true, color: i === 2 ? BLUE : MUTED });
    addText(s, titles[i], { left: xs[i] + 22, top: 266, width: 205, height: 70 },
      { fontSize: 25, bold: true });
    addText(s, bodies[i], { left: xs[i] + 22, top: 350, width: 205, height: 160 },
      { fontSize: 18, color: MUTED });
  }
  addBox(s, { left: 48, top: 578, width: 1152, height: 62 }, BLACK);
  addText(s, "生产运行：Nginx 反向代理 → Azure VM 上的 systemd 服务 → 127.0.0.1:8603 → 持久化任务与报告目录",
    { left: 72, top: 596, width: 1110, height: 28 }, { fontSize: 16, color: WHITE, alignment: "center" });
  addFooter(s);
  addNotes(s, [
    `${sources.repo}/research/2026-08-14/explorer/server.py`,
    `${sources.repo}/research/2026-08-14/explorer/database_builder.py`,
    `${sources.repo}/research/2026-08-14/explorer/deploy_kevindigital.sh`,
  ]);
}

// External sources and collection methods.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "外部数据源：每个站点采用最适合它的采集入口", "Layer 1 · collection", pageNumber++,
    "这一页只看四种采集入口与统一入库过程；Aloruh（SHEIN）的人机协作细节在第5页单独展开。");
  const sourcesRows = [
    ["Princess Polly / Motel Rocks", "SHOPIFY", "/products.json\n250件/页\n集合页补 new / best / sale", "商品 · 变体 · 价格 · 图片URL"],
    ["PrettyLittleThing", "ALGOLIA", "browse index\n1,000件/批＋cursor\n另查索引排名", "商品 · 库存 · 图片 · 热销标记"],
    ["Aloruh local", "WOOCOMMERCE", "Store API\nper_page=100\n保留robots/sitemap快照", "本地商品 · 标签 · 图片"],
    ["Aloruh SHEIN", "BROWSER USE", "真实浏览器会话\n目录与必要详情\n完整流程见第5页", "品牌目录 · 商品详情 · 图片序列"],
  ];
  sourcesRows.forEach((row, i) => {
    const x = 48 + i * 296;
    addBox(s, { left: x, top: 170, width: 278, height: 252 }, i === 3 ? LIGHT_BLUE : PANEL, "none", 8);
    addText(s, row[1], { left: x + 18, top: 190, width: 238, height: 22 },
      { fontSize: 13, typeface: FONT_LATIN, bold: true, color: i === 3 ? BLUE : MUTED });
    addText(s, row[0], { left: x + 18, top: 226, width: 240, height: 46 },
      { fontSize: 20, bold: true });
    addText(s, row[2], { left: x + 18, top: 286, width: 240, height: 84 },
      { fontSize: 16, color: MUTED });
    addText(s, row[3], { left: x + 18, top: 384, width: 240, height: 28 },
      { fontSize: 16, bold: true, color: i === 3 ? BLUE : INK });
  });
  const landingSteps = ["分页读取来源", "保存原始响应", "展开商品与图片URL", "生成稳定键＋去重", "写入SQLite供UI查询"];
  addBox(s, { left: 48, top: 454, width: 1166, height: 182 }, BLACK, "none", 8);
  for (let i = 0; i < 4; i += 1) {
    flowArrow(s, { position: { left: 274 + i * 238, top: 550, width: 36, height: 42 }, color: "#8FD4F2" });
  }
  addText(s, "ALL SOURCES / SHARED LANDING PIPELINE",
    { left: 72, top: 474, width: 620, height: 20 },
    { fontSize: 13, typeface: FONT_LATIN, bold: true, color: "#8FD4F2" });
  landingSteps.forEach((step, i) => {
    const x = 72 + i * 238;
    addText(s, `0${i + 1}`, { left: x, top: 520, width: 36, height: 24 },
      { fontSize: 16, typeface: FONT_LATIN, bold: true, color: "#8FD4F2" });
    addText(s, step, { left: x, top: 552, width: 202, height: 56 },
      { fontSize: 16, bold: true, color: WHITE });
  });
  addFooter(s);
  addNotes(s, [
    `${sources.repo}/research/2026-08-14/scripts/collect_catalogs.py`,
    `${sources.repo}/research/2026-08-14/explorer/database_builder.py`,
    `${sources.repo}/research/2026-08-18/scripts/prepare_aloruh_shein_for_explorer.py`,
  ]);
}

// Live collection inventory by store.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "60,260个商品对应288,831条图片地址，先建索引再按需下载", "Layer 1 · collection inventory", pageNumber++,
    "一条图片索引 = 一个图片URL＋所属店铺、商品和图片位置；它记录“去哪里取图”，本身不是图片文件。");

  const overviewMetrics = [
    ["60,260", "商品记录", false],
    ["288,831", "图片URL索引（非文件）", true],
    ["25,916", "已完成15维分析图片", false],
    ["606,007", "累计分析标签", false],
  ];
  overviewMetrics.forEach((item, index) => {
    const left = 48 + index * 292;
    addText(s, item[0], { left, top: 154, width: 250, height: 52 },
      { fontSize: 40, typeface: FONT_LATIN, bold: true, color: item[2] ? BLUE : INK }, `inventory-metric-${index}`);
    addText(s, item[1], { left, top: 208, width: 250, height: 26 },
      { fontSize: 15, color: MUTED }, `inventory-metric-label-${index}`);
  });

  const inventory = [
    ["Aloruh（SHEIN）", "2,848", "4,352", "343"],
    ["Aloruh local", "10,487", "10,771", "10,466"],
    ["Princess Polly", "17,008", "119,205", "5,613"],
    ["Motel Rocks", "4,422", "26,676", "2,141"],
    ["PrettyLittleThing", "25,495", "127,827", "7,353"],
  ];
  const headerTop = 266;
  addBox(s, { left: 48, top: headerTop, width: 1166, height: 42 }, BLACK, "none", 0, "inventory-table-header");
  const headers = [
    ["店铺", 64, 330],
    ["商品记录", 478, 150],
    ["图片URL索引（条）", 704, 180],
    ["已分析图片", 972, 180],
  ];
  headers.forEach((header, index) => {
    addText(s, header[0], { left: header[1], top: headerTop + 12, width: header[2], height: 20 },
      { fontSize: 13, bold: true, color: WHITE, alignment: index > 0 ? "right" : "left" }, `inventory-header-${index}`);
  });

  inventory.forEach((row, index) => {
    const top = 308 + index * 52;
    if (index % 2 === 1) addBox(s, { left: 48, top, width: 1166, height: 52 }, "#F7F7F7", "none", 0, `inventory-row-bg-${index}`);
    addText(s, row[0], { left: 64, top: top + 15, width: 330, height: 24 },
      { fontSize: 17, bold: true }, `inventory-store-${index}`);
    addText(s, row[1], { left: 478, top: top + 15, width: 150, height: 24 },
      { fontSize: 17, typeface: FONT_LATIN, alignment: "right" }, `inventory-products-${index}`);
    addText(s, row[2], { left: 704, top: top + 15, width: 180, height: 24 },
      { fontSize: 17, typeface: FONT_LATIN, bold: true, alignment: "right" }, `inventory-images-${index}`);
    addText(s, row[3], { left: 972, top: top + 15, width: 180, height: 24 },
      { fontSize: 17, typeface: FONT_LATIN, alignment: "right", color: MUTED }, `inventory-analyzed-${index}`);
    addRule(s, 48, top + 51, 1166, "#E1E3E6");
  });

  addBox(s, { left: 48, top: 582, width: 1166, height: 54 }, BLACK, "none", 0, "inventory-total");
  addText(s, "全站合计", { left: 64, top: 598, width: 250, height: 24 },
    { fontSize: 17, bold: true, color: WHITE }, "inventory-total-label");
  addText(s, "60,260", { left: 478, top: 598, width: 150, height: 24 },
    { fontSize: 17, typeface: FONT_LATIN, bold: true, color: WHITE, alignment: "right" }, "inventory-total-products");
  addText(s, "288,831", { left: 704, top: 598, width: 180, height: 24 },
    { fontSize: 17, typeface: FONT_LATIN, bold: true, color: "#8FD4F2", alignment: "right" }, "inventory-total-images");
  addText(s, "25,916", { left: 972, top: 598, width: 180, height: 24 },
    { fontSize: 17, typeface: FONT_LATIN, bold: true, color: WHITE, alignment: "right" }, "inventory-total-analyzed");
  addText(s, "读法：1个商品若有5张图，就产生5条图片URL索引；本页不统计本地实际下载文件数。",
    { left: 48, top: 646, width: 1166, height: 28 }, { fontSize: 13, color: MUTED }, "inventory-method-note");
  addFooter(s, "Fashion Scope · explorer.db live inventory · 2026-08-26");
  addNotes(s, [
    `${sources.repo}/research/2026-08-14/explorer/explorer.db`,
    `${sources.repo}/research/2026-08-14/explorer/database_builder.py`,
    "Live SQLite aggregate query executed 2026-08-26: products, per-store distinct source_url, analyzed images, and analysis tags.",
  ]);
}

// Aloruh SHEIN collection in detail.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "Aloruh（SHEIN）的采集核心是可暂停、可恢复的人机协同", "Layer 1 · SHEIN deep dive", pageNumber++,
    "Browser Use负责操作真实浏览器；用户本人负责登录与验证码；采集器只导出公开商品卡片和必要详情。");
  metric(s, "26/26", "目录页完成", 48, 150, 220, true);
  metric(s, "3,006", "原始商品卡片", 304, 150, 240);
  metric(s, "150", "抽样商品详情", 574, 150, 220);
  addText(s, "导出文件明确不包含 cookies、tokens、headers、credentials 或风险参数。",
    { left: 832, top: 170, width: 382, height: 64 }, { fontSize: 17, color: MUTED });

  const steps = [
    ["01", "打开真实会话", "Browser Use进入\nSHEIN SG Aloruh\n品牌排序页"],
    ["02", "人工过验证", "用户本人登录\n并处理验证码/\n风险验证"],
    ["03", "逐页取卡片", "page=1…26\n提取商品ID、价格、\n分类、销量文案、图片URL"],
    ["04", "每页写检查点", "记录已完成页码\n遇风险拦截即停\n保留partial文件"],
    ["05", "补必要详情", "对150个目标商品\n读取尺码、颜色、\n更完整图片序列"],
    ["06", "导出可审计原始层", "目录页、商品组\n失败记录、采集状态\n全部保留"],
  ];
  for (let i = 0; i < 5; i += 1) {
    flowArrow(s, { position: { left: 226 + i * 198, top: 382, width: 22, height: 42 } });
  }
  steps.forEach((step, i) => {
    const x = 48 + i * 198;
    addBox(s, { left: x, top: 278, width: 180, height: 250 }, i === 1 ? LIGHT_BLUE : PANEL, "none", 8, `shein-step-${i}`);
    addText(s, step[0], { left: x + 16, top: 296, width: 42, height: 24 },
      { fontSize: 14, typeface: FONT_LATIN, bold: true, color: i === 1 ? BLUE : MUTED });
    addText(s, step[1], { left: x + 16, top: 334, width: 148, height: 48 },
      { fontSize: 19, bold: true });
    addText(s, step[2], { left: x + 16, top: 396, width: 148, height: 110 },
      { fontSize: 16, color: MUTED });
  });
  addBox(s, { left: 48, top: 556, width: 1170, height: 86 }, BLACK, "none", 8);
  addText(s, "恢复策略", { left: 70, top: 578, width: 110, height: 28 },
    { fontSize: 18, bold: true, color: "#8FD4F2" });
  addText(s, "风险拦截时不伪装成功：保留最后完成页、失败页和原因；人工解除验证后从检查点继续，再合并新旧卡片。",
    { left: 190, top: 576, width: 1000, height: 46 }, { fontSize: 17, color: WHITE });
  addFooter(s);
  addNotes(s, [
    `${sources.repo}/research/2026-08-18/data/aloruh_shein_browser_export.json`,
    `${sources.repo}/research/2026-08-18/data/aloruh_shein_browser_export.recollect.partial.json`,
    `${sources.repo}/research/2026-08-18/scripts/prepare_aloruh_shein_for_explorer.py`,
    "User-confirmed Browser Use login and captcha workflow in current conversation, 2026-08-26",
  ]);
}

// Why indexing is fast, and where bytes/model work starts.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "快的是URL索引；高清下载与AI推理只在需要时发生", "Layer 1 → 2 · data movement", pageNumber++,
    "把“商品元数据、图片URL、图片文件、AI结果”拆成不同层，才能快速更新、精确去重并控制费用。");
  flowArrow(s, { position: { left: 390, top: 332, width: 44, height: 48 } });
  flowArrow(s, { position: { left: 762, top: 332, width: 44, height: 48 } });
  const lanes = [
    [48, "01 / URL INDEX", "官方响应已经带 image_urls", "本地展开为 images_*.jsonl\n键：store_id＋product_id＋position\n计算 url_sha256\n不下载图片文件\n因此可以快速形成全量索引"],
    [420, "02 / NORMALIZED DB", "去重后进入SQLite", "商品ID去重\n店铺内 source_url 唯一\n同URL分析一次并复用结果\n15维标签拆入查询表\nUI只分页读取需要的行"],
    [792, "03 / HD + AI", "付费分析才取高清字节", "尝试去缩略图URL\n校验公网主机、格式、尺寸和SHA256\n整体报告任务共享 _image_cache\n缓存损坏或不达高清门槛才重下\n随后由Sol读取detail=high"],
  ];
  lanes.forEach((lane, i) => {
    addBox(s, { left: lane[0], top: 170, width: 360, height: 366 }, i === 2 ? LIGHT_BLUE : PANEL, "none", 8, `data-lane-${i}`);
    addText(s, lane[1], { left: lane[0] + 22, top: 194, width: 310, height: 22 },
      { fontSize: 13, typeface: FONT_LATIN, bold: true, color: i === 2 ? BLUE : MUTED });
    addText(s, lane[2], { left: lane[0] + 22, top: 238, width: 310, height: 64 },
      { fontSize: 23, bold: true });
    addRule(s, lane[0] + 22, 320, 310, i === 2 ? BLUE : INK, 2);
    addText(s, lane[3], { left: lane[0] + 22, top: 344, width: 310, height: 166 },
      { fontSize: 17, color: MUTED });
  });
  addBox(s, { left: 48, top: 566, width: 1104, height: 78 }, BLACK, "none", 8);
  addText(s, "关键边界：url_sha256只证明“URL已索引”；content_sha256或缓存SHA256才证明“图片字节已下载并校验”。",
    { left: 72, top: 588, width: 1056, height: 42 }, { fontSize: 18, bold: true, color: WHITE, alignment: "center" });
  addFooter(s);
  addNotes(s, [
    `${sources.repo}/research/2026-08-14/scripts/collect_catalogs.py`,
    `${sources.repo}/research/2026-08-14/explorer/database_builder.py`,
    `${sources.repo}/research/2026-08-18/scripts/high_resolution_images.py`,
    `${sources.repo}/research/2026-08-18/scripts/report_analysis_runner.py`,
  ]);
}

// Standardized data layer and all 15 dimensions.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "标准化数据层：不同来源被压成同一套商品、图片与15维标签", "Layer 2 · normalization", pageNumber++,
    "每张图片保留 store_id / product_id / position / source_url；每个维度保存标签与置信度。");
  const pipeline = ["原始来源", "商品JSONL", "图片JSONL", "URL/内容去重", "SQLite索引"];
  for (let i = 0; i < 4; i += 1) {
    flowArrow(s, { position: { left: 246 + i * 244, top: 198, width: 36, height: 38 } });
  }
  pipeline.forEach((label, i) => {
    addBox(s, { left: 48 + i * 244, top: 176, width: 208, height: 78 }, i === 4 ? LIGHT_BLUE : PANEL, "none", 8);
    addText(s, label, { left: 62 + i * 244, top: 202, width: 180, height: 30 },
      { fontSize: 18, bold: true, color: i === 4 ? BLUE : INK, alignment: "center" });
  });
  addText(s, "15 DIMENSIONS / FASHION-IMAGE-V2", { left: 48, top: 294, width: 500, height: 26 },
    { fontSize: 14, typeface: FONT_LATIN, bold: true, color: BLUE });
  const groups = [
    ["商品属性", "01 商品类别\n02 廓形与版型\n03 设计元素\n04 穿着场合\n09 材质纹理\n10 色彩图案"],
    ["镜头与呈现", "05 构图\n06 视角动作\n07 卖点部位\n08 拍摄场景\n13 光线\n14 模特状态"],
    ["风格与版面", "11 视觉语言\n12 搭配方式\n15 图文叠加"],
  ];
  groups.forEach((group, i) => {
    const x = 48 + i * 396;
    addRule(s, x, 342, 350, i === 2 ? BLUE : INK, 3);
    addText(s, group[0], { left: x, top: 360, width: 330, height: 38 },
      { fontSize: 23, bold: true });
    addText(s, group[1], { left: x, top: 414, width: 340, height: 168 },
      { fontSize: 18, color: MUTED });
  });
  addBox(s, { left: 48, top: 602, width: 1142, height: 50 }, BLACK);
  addText(s, "标签可多值 · 商品类别单值 · 每维都有 confidence · 新增图片可按固定字典增量分析",
    { left: 72, top: 616, width: 1094, height: 26 }, { fontSize: 16, color: WHITE, alignment: "center" });
  addFooter(s);
  addNotes(s, [
    `${sources.repo}/research/2026-08-18/scripts/fashion_image_analysis.py`,
    `${sources.repo}/research/2026-08-14/explorer/src/imageAnalysis.js`,
    `${sources.repo}/research/2026-08-14/explorer/database_builder.py`,
  ]);
}

// Dimension examples 1–8.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "15维不是抽象概念：前8维把商品与镜头变成可组合条件", "Layer 2 · taxonomy examples 1/2", pageNumber++,
    "每个例子都来自 fashion-image-v2 的受控标签字典；UI显示中文，数据库保存稳定英文代码。");
  const left = [
    ["01", "商品类别 / product_category", "上衣 · 半身裙 · 连衣裙 · 套装", "先回答主售商品是什么；这是唯一必须单值的维度。"],
    ["02", "廓形版型 / silhouette_fit", "修身包体 · 宽松 · A字廓形 · 紧身胸衣式", "用于比较贴体、宽松、A字与结构塑形的展示差异。"],
    ["03", "设计元素 / design_elements", "露背 · 镂空 · 褶皱 · 压褶", "把露背、挖空、褶皱、压褶等具体结构显式化。"],
    ["04", "穿着场合 / occasion", "日常 · 外出聚会 · 度假 · 婚礼宾客", "描述服装适用语境，不等于照片实际拍摄地点。"],
  ];
  const right = [
    ["05", "画面构图 / composition", "全身 · 近景 · 细节特写 · 纯商品图", "区分全身、近景、细节与无模特商品图。"],
    ["06", "视角动作 / view_action", "正面 · 背面 · 行走 · 镜面自拍", "把正面、背面、行走与自拍等观看方式固定下来。"],
    ["07", "卖点部位 / selling_points", "领口 · 腰胯 · 面料纹理 · 整体造型", "记录镜头主要在解释领口、腰胯、面料还是整套造型。"],
    ["08", "拍摄场景 / scene", "中性棚拍 · 街道 · 海滩 · 建筑空间", "描述图片真实背景：棚拍、街道、海滩或建筑空间。"],
  ];
  left.forEach((row, i) => addDimensionEntry(s, {
    left: 48, top: 158 + i * 124, width: 554, index: row[0], title: row[1], tags: row[2], note: row[3],
  }));
  right.forEach((row, i) => addDimensionEntry(s, {
    left: 660, top: 158 + i * 124, width: 554, index: row[0], title: row[1], tags: row[2], note: row[3],
  }));
  addFooter(s);
  addNotes(s, [`${sources.repo}/research/2026-08-18/scripts/fashion_image_analysis.py`]);
}

// Dimension examples 9–15 and label rules.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "后7维补足材质、视觉语言与版面信号", "Layer 2 · taxonomy examples 2/2", pageNumber++,
    "同一张图可在大多数维度返回多个标签，但每个维度都必须给出标签数组和0–1置信度。");
  const left = [
    ["09", "材质纹理 / material_texture", "针织 · 蕾丝 · 缎面感 · 牛仔", "只标记肉眼可见或标题明确支持的纹理，不猜测纤维成分。"],
    ["10", "色彩图案 / color_pattern", "黑色 · 红色 · 花卉图案 · 纯色", "颜色与图案可以并存，例如红色＋纯色。"],
    ["11", "视觉语言 / visual_language", "干净电商风 · 编辑大片感 · 社交UGC · 直接闪光", "描述商业棚拍、编辑感、社交UGC或直接闪光等表达。"],
    ["12", "搭配方式 / styling", "单品展示 · 完整造型 · 叠穿 · 手袋", "记录单品、整套、叠穿以及可见配饰如何参与画面。"],
  ];
  const right = [
    ["13", "光线 / lighting", "柔和漫射光 · 自然日光 · 直接闪光 · 低调暗光", "把柔光、自然光、直闪和低调照明拆成独立可筛选信号。"],
    ["14", "模特状态 / model_state", "无模特 · 站立姿势 · 视线偏离镜头 · 面部裁切", "只记录姿态与可见状态，不推断身份、健康或吸引力。"],
    ["15", "图文叠加 / graphic_overlay", "无叠加 · 文字叠加 · 拼贴 · Logo水印", "识别纯图、文字、拼贴、Logo水印等版面处理。"],
  ];
  left.forEach((row, i) => addDimensionEntry(s, {
    left: 48, top: 158 + i * 124, width: 554, index: row[0], title: row[1], tags: row[2], note: row[3],
  }));
  right.forEach((row, i) => addDimensionEntry(s, {
    left: 660, top: 158 + i * 124, width: 554, index: row[0], title: row[1], tags: row[2], note: row[3],
  }));
  addBox(s, { left: 660, top: 536, width: 554, height: 110 }, BLACK, "none", 8);
  addText(s, "“无法判断”规则", { left: 682, top: 556, width: 210, height: 26 },
    { fontSize: 18, bold: true, color: "#8FD4F2" });
  addText(s, "看不清就返回“无法判断”（UNKNOWN），不再返回其他标签。\n漏图、重复图或非法标签会被程序拒绝。",
    { left: 682, top: 588, width: 510, height: 48 }, { fontSize: 16, color: WHITE });
  addFooter(s);
  addNotes(s, [
    `${sources.repo}/research/2026-08-18/scripts/fashion_image_analysis.py`,
    `${sources.repo}/research/2026-08-18/scripts/azure_openai_fashion_analyzer.py`,
  ]);
}

// AI model split and analysis mechanics.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "Terra负责“可查询标签”，Sol负责“可交付结论”", "Layer 2 → 3 · AI analysis", pageNumber++,
    "两层模型共享图片键与证据上下文，但输入清晰度、触发时机、输出结构和成本完全不同。");
  const lanes = [
    {
      left: 48, eyebrow: "GPT-5.6-TERRA / BATCH TAGGING", title: "批量15维分类",
      lines: [
        ["输入", "图片URL＋标题＋当前分类＋位置；detail=low"],
        ["调度", "默认8图/批、8个worker；只处理未分析且URL去重后的图片"],
        ["Prompt", "受控字典＋可见证据边界＋UNKNOWN＋主售商品规则"],
        ["输出", "15组tags＋15个confidence；strict JSON Schema"],
        ["质控", "增量检查点、4次重试、策略拦截拆批、图片索引校验"],
      ],
      accent: false,
    },
    {
      left: 640, eyebrow: "GPT-5.6-SOL / PAID DEEP ANALYSIS", title: "按需高清精读",
      lines: [
        ["输入", "高清文件＋店铺/商品/品类＋固定筛选条件；detail=high"],
        ["触发", "体验1点击付费分析；体验2启动整体报告专项分析"],
        ["Prompt", "先写可见事实，再解释；每个判断必须有visible_cue"],
        ["输出", "逐图观察、优缺点、建议、证据；再汇总店铺与Section结论"],
        ["质控", "不写CTR/CVR因果；校验图片ID、品牌归属与Section数量"],
      ],
      accent: true,
    },
  ];
  lanes.forEach((lane, laneIndex) => {
    addBox(s, { left: lane.left, top: 166, width: 560, height: 428 }, lane.accent ? LIGHT_BLUE : PANEL, "none", 8, `model-lane-${laneIndex}`);
    addText(s, lane.eyebrow, { left: lane.left + 24, top: 190, width: 510, height: 22 },
      { fontSize: 13, typeface: FONT_LATIN, bold: true, color: lane.accent ? BLUE : MUTED });
    addText(s, lane.title, { left: lane.left + 24, top: 232, width: 510, height: 42 },
      { fontSize: 28, bold: true });
    lane.lines.forEach((line, i) => {
      const y = 302 + i * 56;
      addText(s, line[0], { left: lane.left + 24, top: y, width: 64, height: 24 },
        { fontSize: 16, bold: true, color: lane.accent ? BLUE : INK });
      addText(s, line[1], { left: lane.left + 92, top: y - 2, width: 438, height: 44 },
        { fontSize: 16, color: MUTED });
    });
  });
  addBox(s, { left: 48, top: 612, width: 1152, height: 42 }, BLACK);
  addText(s, "先用Terra把数万张图变成检索空间；只有用户明确付费时，才让Sol读取高清图并写结论。",
    { left: 72, top: 622, width: 1104, height: 24 }, { fontSize: 17, bold: true, color: WHITE, alignment: "center" });
  addFooter(s);
  addNotes(s, [
    `${sources.repo}/research/2026-08-18/scripts/analyze_explorer_images.py`,
    `${sources.repo}/research/2026-08-18/scripts/azure_openai_fashion_analyzer.py`,
    `${sources.repo}/research/2026-08-18/scripts/detailed_visual_analysis.py`,
    `${sources.repo}/research/2026-08-18/scripts/report_analysis_model.py`,
  ]);
}

// Terra classifier: actual code contract and single-call structure.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "第11页：维度相关部分是标签字典，不是15条判断Prompt", "Layer 2 · Terra actual prompt", pageNumber++,
    "代码里只有一条统一判断规则；每个维度后面列出允许返回的受控代码。以下为真实维度行节选。");
  flowArrow(s, { position: { left: 300, top: 214, width: 38, height: 42 } });
  flowArrow(s, { position: { left: 612, top: 214, width: 38, height: 42 } });
  flowArrow(s, { position: { left: 924, top: 214, width: 38, height: 42 } });
  flowNode(s, { position: { left: 48, top: 174, width: 252, height: 122 }, step: "01", title: "每批图片＋上下文", detail: "URL · 标题 · 已有品类 · 位置", accent: true });
  flowNode(s, { position: { left: 338, top: 174, width: 274, height: 122 }, step: "02", title: "统一可见证据规则", detail: "看不清=UNKNOWN · 主售商品优先" });
  flowNode(s, { position: { left: 650, top: 174, width: 274, height: 122 }, step: "03", title: "15个受控字段", detail: "同一次调用全部判断，不拆15次" });
  flowNode(s, { position: { left: 962, top: 174, width: 246, height: 122 }, step: "04", title: "严格JSON返回", detail: "每维标签＋置信度 · 漏项失败", dark: true });

  addCodeBlock(s, { left: 48, top: 326, width: 430, height: 298 }, "统一规则节选", [
    "Use visible evidence and the supplied title/category only.",
    "Select UNKNOWN when a dimension is not observable,",
    "and never combine UNKNOWN with another code.",
    "product_category must have exactly one value.",
    "Other dimensions may have up to five values.",
    "Focus on the primary item sold; accessories belong",
    "in styling unless they are the primary product.",
  ]);
  addCodeBlock(s, { left: 504, top: 326, width: 704, height: 298 }, "5个真实维度行节选（受控标签，不是独立指令）", [
    "product_category: DRESSES, TOPS, SKIRTS, TROUSERS, ... , UNKNOWN",
    "occasion: CASUAL, GOING_OUT, PARTY, DATE_NIGHT, VACATION, ... , UNKNOWN",
    "composition: FULL_BODY, THREE_QUARTER, HALF_BODY, CLOSE_UP, ... , UNKNOWN",
    "view_action: FRONT_VIEW, SIDE_VIEW, BACK_VIEW, TURNING_BACK, WALKING, ...",
    "scene: STUDIO_NEUTRAL, HOME, MIRROR, BEDROOM, GARDEN, STREET, ... , UNKNOWN",
    "",
    "代码没有额外的“occasion判断句”或“scene判断句”；维度语义由字段名、",
    "标签集合、统一可见证据规则与严格输出Schema共同限定。",
  ], true);
  addBox(s, { left: 48, top: 638, width: 1160, height: 26 }, BLACK);
  addText(s, "完整通用规则＋15个标签字典逐字放在附录A1–A4；Sol主流程与修订Prompt见附录A5–A8。",
    { left: 72, top: 642, width: 1112, height: 18 }, { fontSize: 16, color: WHITE, alignment: "center" });
  addFooter(s);
  addNotes(s, [
    `${sources.repo}/research/2026-08-18/scripts/azure_openai_fashion_analyzer.py`,
    `${sources.repo}/research/2026-08-18/scripts/fashion_image_analysis.py`,
  ]);
}

// Sol has different real call patterns for the two experiences.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "真实实现：两种体验调用Sol的方式不同", "Layer 3 · Sol actual calls", pageNumber++,
    "体验1一次调用同时产出逐图观察和店铺比较；体验2先逐图观察，再进行第二次全量证据合成。");
  addPromptBlock(s, { left: 48, top: 166, width: 560, height: 396 }, "体验1 / 单次高精度分析", [
    "输入：固定筛选条件＋用户选中的高清图片（最多24张）。",
    "",
    "真实Prompt要求：先写肉眼可见事实，再写解释；比较场景、景别、动作、光线、色彩、搭配、服装结构、视觉意图与店铺一致性。",
    "",
    "同一次返回：",
    "• 每张图的可见观察、优缺点、建议和证据线索",
    "• 共同模式、店铺差异、各店总结、拍摄规则、A/B假设",
    "",
    "边界：只代表本次选图，不代表各店全量分布。",
  ].join("\n"), true);
  addPromptBlock(s, { left: 640, top: 166, width: 592, height: 396 }, "体验2 / 两阶段报告分析", [
    "阶段A：每8张高清图调用一次Sol，逐图输出10项可见观察、优缺点、证据线索和候选模式。",
    "",
    "阶段B：把全部逐图观察、图片—店铺映射、竞品全量分布和分析范围交给Sol，再生成五个Section。",
    "",
    "每条结论必须返回：推导、样本数、筛选条件、观察字段、支持图、反例图和代表图。",
    "",
    "边界：比例来自全量分布；高清证据图只负责复核。",
  ].join("\n"));
  addBox(s, { left: 48, top: 586, width: 1160, height: 70 }, BLACK, "none", 8);
  addText(s, "Terra先把图片变成可筛选标签；Sol再把指定范围内的图片证据变成解释、比较和建议。",
    { left: 72, top: 606, width: 1112, height: 30 }, { fontSize: 19, bold: true, color: WHITE, alignment: "center" });
  addFooter(s);
  addNotes(s, [
    `${sources.repo}/research/2026-08-18/scripts/detailed_visual_analysis.py`,
    `${sources.repo}/research/2026-08-18/scripts/report_analysis_model.py`,
    `${sources.repo}/research/2026-08-18/scripts/report_analysis_runner.py`,
  ]);
}

// Experience 1 workflow: selection and execution.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "体验1流程①：AND筛选后，手动选图与自动选图走两条真实路径", "Layer 3A · selection flow", pageNumber++,
    "Terra标签只负责缩小候选范围；最终送入Sol的图片由用户明确选择，或由系统按店铺均衡随机选取。");

  flowNode(s, { position: { left: 48, top: 170, width: 226, height: 142 }, step: "01", title: "校验筛选条件", detail: "维度必须属于15维\n标签必须在受控字典" , accent: true });
  flowArrow(s, { position: { left: 274, top: 218, width: 42, height: 42 } });
  flowNode(s, { position: { left: 316, top: 170, width: 226, height: 142 }, step: "02", title: "SQLite执行AND", detail: "每一维都必须命中\nsource_url全局去重" });
  flowArrow(s, { text: "↗", position: { left: 542, top: 178, width: 52, height: 52 } });
  flowArrow(s, { text: "↘", position: { left: 542, top: 262, width: 52, height: 52 } });

  addBox(s, { left: 596, top: 162, width: 612, height: 176 }, LIGHT_BLUE, "none", 8, "manual-lane");
  addText(s, "手动选图", { left: 618, top: 182, width: 130, height: 28 }, { fontSize: 20, bold: true, color: BLUE });
  addText(s, "用户提交 store_id＋product_id＋position；后端再次检查：键唯一、店铺在范围内、图片存在、仍满足AND条件；保持用户选择顺序，最多24张。",
    { left: 618, top: 224, width: 566, height: 86 }, { fontSize: 17, color: INK });

  addBox(s, { left: 596, top: 360, width: 612, height: 190 }, PANEL, "none", 8, "automatic-lane");
  addText(s, "自动选图", { left: 618, top: 380, width: 130, height: 28 }, { fontSize: 20, bold: true });
  addText(s, "先把每店候选池扩到目标数的8倍（单店12–32张、总池不超过160张），再用 SystemRandom 在各店内打乱；按店铺轮询取图，直到每店成功下载1–8张且总数≤24。",
    { left: 618, top: 422, width: 566, height: 102 }, { fontSize: 17, color: MUTED });

  flowArrow(s, { text: "↓", position: { left: 300, top: 320, width: 48, height: 48 } });
  flowNode(s, { position: { left: 48, top: 382, width: 494, height: 168 }, step: "03", title: "下载高清图并明确记录失败", detail: "逐个尝试候选图；达到每店配额后停止。\n阈值：≥80万像素、长边≥1000、短边≥600。\n失败不会静默替代为低清图。" });

  addBox(s, { left: 48, top: 584, width: 1160, height: 66 }, BLACK);
  addText(s, "送入Sol的不是全部命中图，而是最终成功下载并通过高清门槛的1–24张。体验1目前仍按任务下载，尚未接入整体报告的共享高清缓存。",
    { left: 72, top: 600, width: 1112, height: 40 },
    { fontSize: 17, bold: true, color: WHITE, alignment: "center" });
  addFooter(s);
  addNotes(s, [
    sources.production,
    `${sources.repo}/research/2026-08-14/explorer/src/ImageDimensions.jsx`,
    `${sources.repo}/research/2026-08-18/scripts/analyze_dimension_selection.py`,
  ]);
}

// Experience 1 workflow: how the comparison conclusion is produced.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "体验1流程②：一次Sol调用同时返回逐图观察、跨店比较与建议", "Layer 3A · conclusion flow", pageNumber++,
    "这不是先逐图调用、再额外汇总；1–24张高清图与筛选条件被放进同一个请求，由严格JSON一次返回完整结果。");

  addBox(s, { left: 48, top: 166, width: 336, height: 430 }, LIGHT_BLUE, "none", 8, "experience1-input");
  addText(s, "INPUT", { left: 70, top: 188, width: 90, height: 22 }, { fontSize: 14, typeface: FONT_LATIN, bold: true, color: BLUE });
  addText(s, "固定筛选条件", { left: 70, top: 226, width: 270, height: 30 }, { fontSize: 21, bold: true });
  addText(s, "例如 product_category=TOPS AND occasion=VACATION", { left: 70, top: 266, width: 286, height: 62 }, { fontSize: 16, typeface: FONT_LATIN, color: INK });
  addRule(s, 70, 342, 286, "#AFCFE1", 2);
  addText(s, "每张高清图上下文", { left: 70, top: 364, width: 270, height: 28 }, { fontSize: 20, bold: true });
  addText(s, "store · product · title · category · pixels\n图片本体以 detail=high 发送", { left: 70, top: 406, width: 286, height: 74 }, { fontSize: 17, color: INK });
  addText(s, "数量：1–24张", { left: 70, top: 520, width: 200, height: 28 }, { fontSize: 18, bold: true, color: BLUE });

  flowArrow(s, { position: { left: 386, top: 338, width: 48, height: 48 } });
  addBox(s, { left: 434, top: 166, width: 356, height: 430 }, PANEL, "none", 8, "experience1-reasoning");
  addText(s, "SOL PROMPT", { left: 456, top: 188, width: 120, height: 22 }, { fontSize: 14, typeface: FONT_LATIN, bold: true, color: BLUE });
  addText(s, "先事实，后解释", { left: 456, top: 226, width: 290, height: 30 }, { fontSize: 21, bold: true });
  addText(s, "逐图观察：场景、景别、动作、光线、色彩、搭配、服装结构、视觉意图。\n\n每个判断都要 visible_cue；不得推断敏感属性；不得把构图写成CTR/CVR因果。",
    { left: 456, top: 270, width: 310, height: 176 }, { fontSize: 17, color: MUTED });
  addRule(s, 456, 468, 310, "#D0D2D6", 2);
  addText(s, "同一请求内跨图比较", { left: 456, top: 490, width: 286, height: 28 }, { fontSize: 19, bold: true });
  addText(s, "共同模式 · 店铺差异 · 各店视觉定位 · 可复用拍摄规则", { left: 456, top: 532, width: 310, height: 50 }, { fontSize: 16, color: MUTED });

  flowArrow(s, { position: { left: 792, top: 338, width: 48, height: 48 } });
  addBox(s, { left: 840, top: 166, width: 368, height: 430 }, BLACK, "none", 8, "experience1-output");
  addText(s, "STRICT JSON OUTPUT", { left: 862, top: 188, width: 190, height: 22 }, { fontSize: 14, typeface: FONT_LATIN, bold: true, color: "#8FD4F2" });
  addText(s, "逐图结果", { left: 862, top: 226, width: 200, height: 30 }, { fontSize: 21, bold: true, color: WHITE });
  addText(s, "7项可见字段 · visual_intent\nstrengths · weaknesses · changes\nevidence claim＋visible_cue · confidence",
    { left: 862, top: 270, width: 320, height: 112 }, { fontSize: 16, typeface: FONT_LATIN, color: "#D7D7D7" });
  addText(s, "跨图结果", { left: 862, top: 414, width: 200, height: 30 }, { fontSize: 21, bold: true, color: WHITE });
  addText(s, "selection thesis · shared patterns\ncross-store differences · store summaries\nshot system · A/B hypotheses",
    { left: 862, top: 458, width: 320, height: 104 }, { fontSize: 16, typeface: FONT_LATIN, color: "#D7D7D7" });

  addBox(s, { left: 48, top: 620, width: 1160, height: 34 }, BLACK);
  addText(s, "结论只代表本次成功送入Sol的图片；没有全店分布，不得外推整店占比。图片索引和店铺摘要缺失或重复会直接失败。",
    { left: 72, top: 627, width: 1112, height: 20 }, { fontSize: 16, color: WHITE, alignment: "center" });
  addFooter(s);
  addNotes(s, [
    `${sources.repo}/research/2026-08-18/scripts/analyze_dimension_selection.py`,
    `${sources.repo}/research/2026-08-18/scripts/detailed_visual_analysis.py`,
  ]);
}

// Experience 1 screenshot walkthrough.
const experience1Demos = [
  {
    title: "体验1 Demo：进入维度分析，先看可用范围", eyebrow: "Layer 3A · demo 1/7",
    subtitle: "入口先告诉用户已有25,916张分析图、15个维度，以及AND组合筛选规则。",
    imageName: "experience1-step1-enter-dimensions.png", step: "STEP 01 / 07", summary: "进入图片维度分析",
    details: ["确认已有分析图片规模", "查看15个维度与可用标签", "此时还没有筛选结果"],
  },
  {
    title: "体验1 Demo：选择需要组合的分析维度", eyebrow: "Layer 3A · demo 2/7",
    subtitle: "示例选择“商品类别”和“穿着场景”，页面同步生成两个标签下拉框。",
    imageName: "experience1-step2-select-dimensions.png", step: "STEP 02 / 07", summary: "勾选两个维度",
    details: ["商品类别", "穿着场景", "其余维度保持未选"],
  },
  {
    title: "体验1 Demo：把标签组合成可解释的AND条件", eyebrow: "Layer 3A · demo 3/7",
    subtitle: "商品类别=上衣，穿着场景=度假；只有同时满足两个标签的图片才会命中。",
    imageName: "experience1-step3-and-filter.png", step: "STEP 03 / 07", summary: "设定“上衣 AND 度假”",
    details: ["每个维度只取一个标签", "条件之间使用AND", "生产结果即时刷新"],
  },
  {
    title: "体验1 Demo：结果按店铺拆分，并保留商品证据", eyebrow: "Layer 3A · demo 4/7",
    subtitle: "生产环境命中3,179张；每张卡片都保留店铺、商品ID、标签与原图。",
    imageName: "experience1-step4-matched-results.png", step: "STEP 04 / 07", summary: "查看匹配结果",
    details: ["命中3,179张", "按5家店分别展示", "可继续打开单图证据"],
  },
  {
    title: "体验1 Demo：手动选图，确认付费分析范围", eyebrow: "Layer 3A · demo 5/7",
    subtitle: "勾选2张图并切换为手动选图；界面明确显示将分析1家店、2张高清图。",
    imageName: "experience1-step5-select-for-analysis.png", step: "STEP 05 / 07", summary: "选择精读样本",
    details: ["手动勾选2张图片", "确认1家店、2张高清图", "费用提示在点击前可见"],
  },
  {
    title: "体验1 Demo：点击付费分析，实时查看运行状态", eyebrow: "Layer 3A · demo 6/7",
    subtitle: "点击一次“开始精细视觉分析（付费）”后，按钮锁定并持续显示GPT-5.6 Sol任务进度。",
    imageName: "experience1-step6-analysis-running.png", step: "STEP 06 / 07", summary: "启动付费分析",
    details: ["付费按钮只触发一次", "运行中按钮自动锁定", "实时进度显示为55%"],
  },
  {
    title: "体验1 Demo：结果同时给出结论、Token与费用", eyebrow: "Layer 3A · demo 7/7",
    subtitle: "2张高清图在81.3秒内完成；页面返回总体结论、共同模式、店铺差异和逐图可验证建议。",
    imageName: "experience1-step7-analysis-result.png", step: "STEP 07 / 07", summary: "查看精细分析结果",
    details: ["2/2图片成功、无失败", "总Token 8,343", "预估费用 $0.1897"],
  },
];
for (const demo of experience1Demos) {
  await addDemoSlide({ ...demo, page: pageNumber++ });
}

// Experience 2 workflow: build the evidence base.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "体验2流程①：竞品按“店铺×品类”分层选证据", "Layer 3B · evidence selection", pageNumber++,
    "15,107张竞品首图负责计算分布；高清证据图只负责让视觉判断可复核，不能替代全量分母。");

  addBox(s, { left: 48, top: 166, width: 264, height: 442 }, LIGHT_BLUE, "none", 8, "target-population");
  addText(s, "目标店铺", { left: 70, top: 188, width: 180, height: 28 }, { fontSize: 21, bold: true, color: BLUE });
  addText(s, "Aloruh · TOPS＋SKIRTS", { left: 70, top: 230, width: 216, height: 28 }, { fontSize: 16, typeface: FONT_LATIN, bold: true });
  metric(s, "415", "计划进入下载的全量首图", 70, 286, 190, true);
  addRule(s, 70, 404, 216, "#AFCFE1", 2);
  addText(s, "规则", { left: 70, top: 430, width: 80, height: 24 }, { fontSize: 18, bold: true });
  addText(s, "范围内全部首图都进入下载队列，不使用标签筛掉目标店铺图片。成功下载386张。",
    { left: 70, top: 470, width: 216, height: 112 }, { fontSize: 17, color: INK });

  addBox(s, { left: 336, top: 166, width: 366, height: 442 }, PANEL, "none", 8, "competitor-population");
  addText(s, "竞品全量分母", { left: 358, top: 188, width: 220, height: 28 }, { fontSize: 21, bold: true });
  addText(s, "3家竞品 × 2个品类 = 6个独立池", { left: 358, top: 230, width: 316, height: 28 }, { fontSize: 17, color: MUTED });
  metric(s, "15,107", "张竞品首图参与分布统计", 358, 286, 230);
  addRule(s, 358, 404, 316, "#D0D2D6", 2);
  addText(s, "每个池都读取6维标签", { left: 358, top: 430, width: 290, height: 28 }, { fontSize: 18, bold: true });
  addText(s, "穿着场合 · 拍摄场景 · 画面构图\n视角动作 · 视觉语言 · 搭配方式\n缺任一维标签，整个池直接失败。",
    { left: 358, top: 472, width: 316, height: 100 }, { fontSize: 17, color: MUTED });

  addBox(s, { left: 726, top: 166, width: 482, height: 442 }, BLACK, "none", 8, "competitor-selection-algorithm");
  addText(s, "每个竞品×品类池的选图算法", { left: 750, top: 188, width: 410, height: 30 }, { fontSize: 21, bold: true, color: WHITE });
  const selectionSteps = [
    ["01", "每一维按全量标签计数与占比排序"],
    ["02", "选最高频2个标签＋达到约0.5%门槛后最少见的1个边界标签"],
    ["03", "代表图按标签置信度最高 → catalog rank → product ID选出"],
    ["04", "每图取6维最高置信度标签，形成六维组合签名"],
    ["05", "组合簇再选Top 2＋有效边界1；最后跨维、理由、URL去重"],
  ];
  selectionSteps.forEach((row, index) => {
    const y = 244 + index * 64;
    addText(s, row[0], { left: 750, top: y, width: 34, height: 22 },
      { fontSize: 14, typeface: FONT_LATIN, bold: true, color: "#8FD4F2" });
    addText(s, row[1], { left: 796, top: y - 2, width: 384, height: 50 },
      { fontSize: 16, color: "#D7D7D7" });
  });
  addText(s, "结果：计划107张竞品证据图；成功下载106张", { left: 750, top: 566, width: 420, height: 24 },
    { fontSize: 17, bold: true, color: WHITE });

  addBox(s, { left: 48, top: 628, width: 1160, height: 30 }, BLACK);
  addText(s, "目标=全量进入；竞品=全量算分布后选典型/边界证据。两者进入Sol前都保留 store、product、category、role 与 selection_reasons。",
    { left: 70, top: 634, width: 1116, height: 18 }, { fontSize: 16, color: WHITE, alignment: "center" });
  addFooter(s);
  addNotes(s, [
    `${sources.repo}/research/2026-08-18/scripts/report_analysis_runner.py`,
    `${sources.repo}/research/2026-08-18/scripts/report_analysis_model.py`,
  ]);
}

// Experience 2 workflow: synthesize, validate, review, and render.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "体验2流程②：成功下载的492张图片全部逐图分析，没有再抽一层", "Layer 3B · per-image analysis", pageNumber++,
    "计划选入522张；30张高清下载失败后，386张目标图＋106张竞品图全部进入Sol逐图观察。");

  const counts = [
    ["计划范围", "522", "415目标＋107竞品"],
    ["成功下载", "492", "386目标＋106竞品"],
    ["下载失败", "30", "记录图片/店铺/商品/错误"],
    ["逐图批次", "62", "每批最多8张"],
  ];
  counts.forEach((item, index) => {
    const left = 48 + index * 290;
    addBox(s, { left, top: 166, width: 266, height: 142 }, index === 1 ? LIGHT_BLUE : PANEL, "none", 8, `count-${index}`);
    addText(s, item[0], { left: left + 20, top: 184, width: 120, height: 22 }, { fontSize: 16, bold: true, color: index === 1 ? BLUE : MUTED });
    addText(s, item[1], { left: left + 20, top: 218, width: 100, height: 54 }, { fontSize: 38, typeface: FONT_LATIN, bold: true, color: index === 1 ? BLUE : INK });
    addText(s, item[2], { left: left + 114, top: 224, width: 132, height: 58 }, { fontSize: 16, color: INK });
  });

  flowArrow(s, { text: "↓", position: { left: 600, top: 314, width: 48, height: 48 } });
  addBox(s, { left: 48, top: 370, width: 740, height: 246 }, BLACK, "none", 8, "per-image-output");
  addText(s, "每张图必须返回的可见观察", { left: 72, top: 392, width: 320, height: 30 }, { fontSize: 21, bold: true, color: WHITE });
  addText(s, "scene · framing · pose_action · lighting · palette\nstyling · garment_display · first_image_type · brand_signal · text_overlay",
    { left: 72, top: 438, width: 690, height: 66 }, { fontSize: 17, typeface: FONT_LATIN, color: "#D7D7D7" });
  addText(s, "＋ visual_role · strengths · weaknesses · evidence_cues（至少2条）· confidence",
    { left: 72, top: 528, width: 690, height: 28 }, { fontSize: 17, typeface: FONT_LATIN, color: "#8FD4F2" });
  addText(s, "每批同时返回2–10个候选模式，并列支持图与反例图。批内图片ID缺失或重复，整批失败。",
    { left: 72, top: 572, width: 690, height: 28 }, { fontSize: 16, color: WHITE });

  addBox(s, { left: 814, top: 370, width: 394, height: 246 }, LIGHT_BLUE, "none", 8, "merged-evidence");
  addText(s, "汇总证据包", { left: 836, top: 392, width: 220, height: 30 }, { fontSize: 21, bold: true, color: BLUE });
  addText(s, "492张逐图观察\n全部批次候选模式\n图片—店铺—商品—角色映射\n15,107张竞品全量标签分布\n竞品证据图的入选原因\n报告范围与排除指标",
    { left: 836, top: 438, width: 346, height: 158 }, { fontSize: 17, color: INK });

  addBox(s, { left: 48, top: 636, width: 1160, height: 24 }, BLACK);
  addText(s, "然后只进行1次Sol汇总调用，同时生成五个Section；总调用数=62次逐图批次＋1次汇总。",
    { left: 72, top: 639, width: 1112, height: 18 }, { fontSize: 16, color: WHITE, alignment: "center" });
  addFooter(s);
  addNotes(s, [
    `${sources.repo}/research/2026-08-18/scripts/report_analysis_runner.py`,
    `${sources.repo}/research/2026-08-18/scripts/report_analysis_model.py`,
  ]);
}

// Experience 2 workflow: explain how the five sections are produced.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "体验2流程③：五个Section共享同一证据包，不是五次独立分析", "Layer 3B · five-section logic", pageNumber++,
    "一次Sol汇总响应同时返回五章。章节语义由section_id、中文标题和统一Prompt限定；观察字段分工不是程序硬编码。");

  const rows = [
    ["品牌视觉定位校准", "目标店铺逐图观察", "常用：brand_signal · palette · styling · scene", "Prompt语义约束；2–6条claim"],
    ["商品展示分析", "目标店铺逐图观察", "常用：garment_display · framing · first_image_type", "Prompt语义约束；2–6条claim"],
    ["店铺视觉审计", "目标店铺跨图观察", "常用：scene · lighting · palette · 一致性", "Prompt语义约束；2–6条claim"],
    ["竞品视觉差距", "目标观察＋竞品分布＋106图", "6维全量占比＋10项高清观察", "三品牌点名＋品牌证据硬校验"],
    ["视觉升级方向", "同一完整证据包", "把可见问题转成拍摄/图序/表达建议", "与前四章同时生成；无顺序依赖"],
  ];
  const colX = [48, 314, 574, 892];
  const colW = [250, 244, 302, 316];
  ["SECTION", "主要证据范围", "模型可用的判断视角", "真实约束"].forEach((title, index) => {
    addBox(s, { left: colX[index], top: 164, width: colW[index], height: 46 }, index === 0 ? BLACK : PANEL);
    addText(s, title, { left: colX[index] + 14, top: 176, width: colW[index] - 28, height: 22 },
      { fontSize: 16, typeface: index === 0 ? FONT_LATIN : FONT, bold: true, color: index === 0 ? WHITE : INK });
  });
  rows.forEach((row, rowIndex) => {
    const y = 216 + rowIndex * 82;
    row.forEach((value, colIndex) => {
      addBox(s, { left: colX[colIndex], top: y, width: colW[colIndex], height: 74 }, rowIndex === 3 && colIndex === 3 ? LIGHT_BLUE : WHITE, "#D7D9DD");
      addText(s, value, { left: colX[colIndex] + 14, top: y + 12, width: colW[colIndex] - 28, height: 52 },
        { fontSize: 16, bold: colIndex === 0, color: rowIndex === 3 && colIndex === 3 ? BLUE : colIndex === 0 ? INK : MUTED });
    });
  });
  addBox(s, { left: 48, top: 638, width: 1160, height: 24 }, BLACK);
  addText(s, "重要：第五章不是读取前四章成品后再计算；五章在同一JSON响应里同时形成。",
    { left: 72, top: 641, width: 1112, height: 18 }, { fontSize: 16, bold: true, color: WHITE, alignment: "center" });
  addFooter(s);
  addNotes(s, [
    `${sources.repo}/research/2026-08-18/scripts/report_analysis_model.py`,
    `${sources.repo}/research/2026-08-18/scripts/report_analysis_runner.py`,
  ]);
}

// Experience 2 workflow: claim contract, hard checks, review, and PDF.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "体验2流程④：每条结论如何从观察进入可审核PDF", "Layer 3B · claim contract", pageNumber++,
    "Sol写结论与推导；JSON Schema固定证据字段；程序阻断错误ID和竞品错配；用户逐章决定是否采用。");

  const nodes = [
    ["01", "Sol生成结论", "结论＋推导\n每章2–6条"],
    ["02", "证据范围", "样本数＋筛选条件\n观察字段"],
    ["03", "图片证据", "支持图＋反例图\n代表图"],
    ["04", "程序硬校验", "五章齐全且不重复\nID必须来自输入"],
    ["05", "人工审核", "满意=通过\n不满意=仅重跑该章"],
    ["06", "本地排版PDF", "五章全通过后生成\n不再调用模型"],
  ];
  for (let i = 0; i < 5; i += 1) {
    flowArrow(s, { position: { left: 230 + i * 196, top: 250, width: 34, height: 42 } });
  }
  nodes.forEach((node, index) => {
    flowNode(s, {
      position: { left: 48 + index * 196, top: 178, width: 176, height: 190 },
      step: node[0], title: node[1], detail: node[2], accent: index === 1, dark: index === 5,
    });
  });

  addBox(s, { left: 48, top: 408, width: 560, height: 196 }, LIGHT_BLUE, "none", 8, "hard-validation");
  addText(s, "程序硬校验（失败就不出报告）", { left: 70, top: 430, width: 420, height: 28 }, { fontSize: 20, bold: true, color: BLUE });
  addText(s, "• 每批逐图观察必须恰好覆盖输入图片ID\n• 五个section_id必须各出现一次\n• 每条claim引用的图片ID必须来自492张输入\n• competitive_gap必须分别点名三家竞品，且支持/代表图属于对应品牌",
    { left: 70, top: 474, width: 510, height: 110 }, { fontSize: 17, color: INK });

  addBox(s, { left: 632, top: 408, width: 576, height: 196 }, PANEL, "none", 8, "soft-validation");
  addText(s, "Prompt软约束＋人工审核", { left: 654, top: 430, width: 360, height: 28 }, { fontSize: 20, bold: true });
  addText(s, "• 非竞品章节只用目标店铺证据，当前主要靠Prompt约束\n• 五章具体语义没有五套独立字段公式\n• 视觉升级章与前四章同时生成，不是程序串行推导\n• 不满意时携带原章节、审核意见、scope和完整evidence单章重跑",
    { left: 654, top: 474, width: 526, height: 110 }, { fontSize: 17, color: MUTED });

  addFooter(s);
  addNotes(s, [
    `${sources.repo}/research/2026-08-18/scripts/report_analysis_model.py`,
    `${sources.repo}/research/2026-08-18/scripts/report_analysis_runner.py`,
    `${sources.repo}/research/2026-08-14/explorer/src/Reports.jsx`,
  ]);
}

// Experience 2 screenshot walkthrough.
const experience2Demos = [
  {
    title: "体验2 Demo：先确认报告范围与证据契约", eyebrow: "Layer 3B · demo 1/5",
    subtitle: "用户主动启动专项分析；界面提前说明目标范围、竞品选证据规则、五个Section与费用边界。",
    imageName: "experience2-step1-start-report.png", step: "STEP 01 / 05", summary: "确认后再启动",
    details: ["目标：Aloruh Tops＋Skirts", "竞品以全量分布为分母", "按钮明确提示会产生费用"],
  },
  {
    title: "体验2 Demo：分析完成后先看统计与草稿", eyebrow: "Layer 3B · demo 2/5",
    subtitle: "已完成任务展示386张目标图、15,107张竞品分母、106张高清证据及成本统计。",
    imageName: "experience2-step2-completed-analysis.png", step: "STEP 02 / 05", summary: "打开已完成任务",
    details: ["目标店铺全量逐图分析", "三家竞品分布＋高清证据", "PDF本地排版成本为0"],
  },
  {
    title: "体验2 Demo：逐条检查结论、推导与图片证据", eyebrow: "Layer 3B · demo 3/5",
    subtitle: "每个Section先展示结论，再展示怎么得到、样本范围、观察字段、支持图与反例图。",
    imageName: "experience2-step3-review-section.png", step: "STEP 03 / 05", summary: "审核Section证据链",
    details: ["结论与推导同屏", "图片直接展示，不只显示ID", "店铺归属与样本范围可回查"],
  },
  {
    title: "体验2 Demo：每个Section独立通过或退回", eyebrow: "Layer 3B · demo 4/5",
    subtitle: "审核区同时保留“满意 / 不满意”入口；当前章节显示已通过，下一章节继续审核。",
    imageName: "experience2-step4-approve-section.png", step: "STEP 04 / 05", summary: "逐章做人工判断",
    details: ["支持图与反例图已展开", "审核状态显示已通过", "未通过章节可单独修订"],
  },
  {
    title: "体验2 Demo：五章通过后生成或下载最终PDF", eyebrow: "Layer 3B · demo 5/5",
    subtitle: "第二步只读取已通过草稿进行本地排版；可浏览或下载PDF，不再调用模型。",
    imageName: "experience2-step5-final-pdf.png", step: "STEP 05 / 05", summary: "交付最终PDF",
    details: ["生成、浏览、下载三种动作", "排版0 Token / 0模型费用", "结论与证据进入固定版式"],
  },
];
for (const demo of experience2Demos) {
  await addDemoSlide({ ...demo, page: pageNumber++ });
}

// PDF section map.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "53 页成品由五个 Section 逐层收敛到行动方案", "PDF structure", pageNumber++,
    "每个章节都回答一个不同的问题，并保留代表图、支持图、反例图与推导方法。");
  const items = [
    ["page-04.jpg", "品牌视觉定位校准", "P2–6", "我们到底像什么？"],
    ["page-14.jpg", "商品展示分析", "P7–14", "商品信息是否可读？"],
    ["page-22.jpg", "店铺视觉审计", "P15–25", "浏览体验哪里失序？"],
    ["page-27.jpg", "竞品视觉差距", "P26–39", "差距来自什么系统？"],
    ["page-44.jpg", "视觉升级方向", "P40–53", "下一步怎么改？"],
  ];
  for (let i = 0; i < items.length; i += 1) {
    const x = 48 + i * 238;
    await addImage(s, items[i][0], { left: x, top: 175, width: 220, height: 124 }, { alt: items[i][1] });
    addText(s, items[i][2], { left: x, top: 322, width: 220, height: 26 },
      { fontSize: 16, typeface: FONT_LATIN, bold: true, color: BLUE });
    addText(s, items[i][1], { left: x, top: 360, width: 220, height: 72 },
      { fontSize: 23, bold: true });
    addText(s, items[i][3], { left: x, top: 450, width: 220, height: 60 },
      { fontSize: 16, color: MUTED });
  }
  addBox(s, { left: 48, top: 558, width: 1152, height: 74 }, PANEL);
  addText(s, "共同证据契约", { left: 70, top: 578, width: 190, height: 28 }, { fontSize: 17, bold: true });
  addText(s, "范围与分母清楚 · 图片角色清楚 · 店铺归属清楚 · 结论能够回查到 image_id",
    { left: 280, top: 578, width: 890, height: 30 }, { fontSize: 17, color: MUTED });
  addFooter(s);
  addNotes(s, [`${sources.repo}/research/2026-08-14/explorer/report_pdf_pages.py`, `${sources.repo}/tmp/pdfs/production-semantic-22a1362.pdf`]);
}

// Finished artifact showcase.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "成品不是图册，而是一套可复用的视觉诊断语言", "Finished artifact", pageNumber++,
    "从品牌母题、品类图法、店铺秩序、竞品系统，最终落到可执行的视觉系列方案。");
  await addImage(s, "page-48.jpg", { left: 500, top: 156, width: 730, height: 411 }, { alt: "Hero image optimization example" });
  await addImage(s, "page-09.jpg", { left: 48, top: 156, width: 212, height: 119 }, { alt: "Tops visual analysis example" });
  await addImage(s, "page-28.jpg", { left: 276, top: 156, width: 212, height: 119 }, { alt: "Competitor visual system example" });
  await addImage(s, "page-51.jpg", { left: 48, top: 295, width: 440, height: 247 }, { alt: "Final reference board example" });
  metric(s, "53", "页视觉诊断", 48, 574, 160, true);
  metric(s, "5", "个可审核 Section", 230, 574, 200);
  addText(s, "成品文件", { left: 500, top: 594, width: 120, height: 22 }, { fontSize: 16, bold: true, color: MUTED });
  addText(s, "Aloruh纯视觉诊断－图片结论版.pdf", { left: 620, top: 588, width: 580, height: 32 },
    { fontSize: 18, bold: true });
  addFooter(s, "Fashion Scope · final report rendered and visually checked page by page");
  addNotes(s, [`${sources.repo}/tmp/pdfs/production-semantic-22a1362.pdf`, `${sources.repo}/tmp/pdfs/semantic-pages-22a1362/`]);
}

// Appendix A1: complete Terra prompt, general rules and dimensions 1–3.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "附录A1/8：Terra完整Prompt — 通用规则＋维度1–3", "Prompt appendix · code verbatim", pageNumber++,
    "以下文本来自_taxonomy_prompt()；仅为适配页面人工换行，单词与标签未改写。");
  addCodeBlock(s, { left: 48, top: 164, width: 1160, height: 246 }, "统一规则（完整）", [
    "Analyze every numbered fashion image using exactly the controlled codes below. Use visible",
    "evidence and the supplied title/category only. Select UNKNOWN when a dimension is not observable,",
    "and never combine UNKNOWN with another code. Do not infer ethnicity, health, attractiveness or",
    "other sensitive traits. product_category must have exactly one value. Other dimensions may have",
    "up to five values. Focus on the primary item sold; accessories belong in styling unless they are",
    "the primary product. Return every image once.",
  ], true);
  addCodeBlock(s, { left: 48, top: 432, width: 1160, height: 214 }, "受控标签字典 01–03 / 15", [
    "product_category: DRESSES, TOPS, SKIRTS, TROUSERS, SHORTS, SWIMWEAR, OUTERWEAR, JEANS, JUMPSUITS, PLAYSUITS, SETS, LINGERIE, ACCESSORIES, SHOES, OTHER, UNKNOWN",
    "silhouette_fit: BODYCON, FITTED, SLIM, REGULAR, RELAXED, OVERSIZED, A_LINE, STRAIGHT, FLARED, DRAPED, CORSETED, UNKNOWN",
    "design_elements: BACKLESS, CUTOUT, HALTER, OFF_SHOULDER, STRAPLESS, SPAGHETTI_STRAP, LACE_UP, SLIT, RUFFLE, TIE_DETAIL, RUCHED, ASYMMETRIC, SHEER_PANEL, EMBELLISHED, PLEATED, UNKNOWN",
  ]);
  addFooter(s);
  addNotes(s, [
    `${sources.repo}/research/2026-08-18/scripts/azure_openai_fashion_analyzer.py`,
    `${sources.repo}/research/2026-08-18/scripts/fashion_image_analysis.py`,
  ]);
}

// Appendix A2: complete Terra prompt, dimensions 4–8.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "附录A2/8：Terra完整Prompt — 维度4–8", "Prompt appendix · code verbatim", pageNumber++,
    "这些维度行紧接在统一规则后面；它们是允许返回的代码集合，不是五次独立请求。");
  addCodeBlock(s, { left: 48, top: 164, width: 1160, height: 486 }, "受控标签字典 04–08 / 15", [
    "occasion: CASUAL, GOING_OUT, PARTY, DATE_NIGHT, VACATION, BEACH, POOL, WEDDING_GUEST, FESTIVAL, COMMUTE, FORMAL, HOME, UNKNOWN",
    "",
    "composition: FULL_BODY, THREE_QUARTER, HALF_BODY, CLOSE_UP, DETAIL, FLAT_LAY, PRODUCT_ONLY, UNKNOWN",
    "",
    "view_action: FRONT_VIEW, SIDE_VIEW, BACK_VIEW, TURNING_BACK, WALKING, SITTING, STANDING, MIRROR_SELFIE, HAIR_MOVED, LOOKING_AWAY, INTERACTING_WITH_SCENE, UNKNOWN",
    "",
    "selling_points: NECKLINE, SHOULDERS, BACK, WAIST, WAIST_HIP, LEGS, HEMLINE, SLEEVES, FABRIC_TEXTURE, DRAPE, PRINT, FULL_OUTFIT, UNKNOWN",
    "",
    "scene: STUDIO_NEUTRAL, HOME, MIRROR, BEDROOM, GARDEN, STREET, BEACH, POOL, PARTY, NIGHT, ARCHITECTURE, NATURE, OTHER, UNKNOWN",
  ], true);
  addFooter(s);
  addNotes(s, [`${sources.repo}/research/2026-08-18/scripts/fashion_image_analysis.py`]);
}

// Appendix A3: complete Terra prompt, dimensions 9–12.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "附录A3/8：Terra完整Prompt — 维度9–12", "Prompt appendix · code verbatim", pageNumber++,
    "长标签行按页面宽度自动换行；标签拼写与代码完全一致。");
  addCodeBlock(s, { left: 48, top: 164, width: 1160, height: 486 }, "受控标签字典 09–12 / 15", [
    "material_texture: KNIT, LACE, SATIN_LIKE, SILK_LIKE, DENIM, COTTON_LIKE, CHIFFON, MESH, SEQUIN, LEATHER_LIKE, RIBBED, CROCHET, PLEATED, UNKNOWN",
    "",
    "color_pattern: COLOR_BLACK, COLOR_WHITE, COLOR_GREY, COLOR_BEIGE, COLOR_BROWN, COLOR_RED, COLOR_PINK, COLOR_ORANGE, COLOR_YELLOW, COLOR_GREEN, COLOR_BLUE, COLOR_PURPLE, COLOR_METALLIC, COLOR_MULTI, PATTERN_SOLID, PATTERN_FLORAL, PATTERN_STRIPE, PATTERN_CHECK, PATTERN_ANIMAL, PATTERN_ABSTRACT, PATTERN_GRAPHIC, UNKNOWN",
    "",
    "visual_language: ECOMMERCE_CLEAN, EDITORIAL, LIFESTYLE, SOCIAL_UGC, ROMANTIC, VINTAGE, Y2K, MINIMAL, GLAMOROUS, SOFT_LIGHT, NATURAL_LIGHT, DIRECT_FLASH, WARM_TONE, COOL_TONE, UNKNOWN",
    "",
    "styling: SINGLE_ITEM, FULL_LOOK, LAYERED, ACCESSORIES_VISIBLE, HANDBAG, SHOES_VISIBLE, JEWELRY, MATCHING_SET, SWIM_COVERUP, UNKNOWN",
  ], true);
  addFooter(s);
  addNotes(s, [`${sources.repo}/research/2026-08-18/scripts/fashion_image_analysis.py`]);
}

// Appendix A4: complete Terra prompt, dimensions 13–15 and request wrapper.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "附录A4/8：Terra完整Prompt — 维度13–15＋请求封装", "Prompt appendix · complete request", pageNumber++,
    "至此通用规则与15个维度已完整列出；同一请求还会为每张图片追加上下文，并使用严格JSON Schema。");
  addCodeBlock(s, { left: 48, top: 164, width: 1160, height: 264 }, "受控标签字典 13–15 / 15", [
    "lighting: SOFT_DIFFUSED, NATURAL_DAYLIGHT, HARD_DIRECT, DIRECT_FLASH, WARM_AMBIENT, COOL_AMBIENT, LOW_KEY, HIGH_KEY, MIXED_LIGHT, UNKNOWN",
    "",
    "model_state: NO_MODEL, STANDING_POSE, WALKING_MOTION, SITTING_POSE, LOOKING_CAMERA, LOOKING_AWAY, FACE_CROPPED, MIRROR_SELFIE, INTERACTING, UNKNOWN",
    "",
    "graphic_overlay: NONE, TEXT_OVERLAY, PRICE_PROMOTION, LOGO_WATERMARK, COLLAGE, FRAME_BORDER, STICKER_GRAPHIC, UI_SCREENSHOT, UNKNOWN",
  ], true);
  addCodeBlock(s, { left: 48, top: 452, width: 564, height: 190 }, "每图追加的真实上下文格式", [
    "IMAGE {index}; key={item.key}; title={title|unknown};",
    "current_category={category|unknown}; position={position}",
    "＋ input_image(detail=low)",
  ]);
  addCodeBlock(s, { left: 636, top: 452, width: 572, height: 190 }, "严格输出契约", [
    "items[]: i + tags{15 dimensions} + confidence{15 dimensions}",
    "product_category exactly 1; other dimensions 1–5 values",
    "每张输入图必须恰好返回一次；漏图、重复图、漏维度均失败。",
  ]);
  addFooter(s);
  addNotes(s, [
    `${sources.repo}/research/2026-08-18/scripts/azure_openai_fashion_analyzer.py`,
    `${sources.repo}/research/2026-08-18/scripts/fashion_image_analysis.py`,
  ]);
}

// Appendix A5: complete Experience 1 Sol prompt.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "附录A5/8：体验1 Sol完整Prompt", "Prompt appendix · experience 1", pageNumber++,
    "代码原文来自detailed_visual_analysis.py；固定筛选条件在末尾以JSON拼接。");
  addCodeBlock(s, { left: 48, top: 164, width: 1160, height: 330 }, "_prompt(filters) 完整文本", [
    "你是一名电商女装视觉策略负责人。请对同一固定维度组合下的多店铺高清商品图做精细视觉分析，输出中文。",
    "先写肉眼可见事实，再写解释；每个判断都要给 visible_cue。不要推断种族、健康、吸引力等敏感属性。",
    "不要把构图相关性写成 CTR/CVR 因果；经营影响只能写成待 A/B 验证的假设。重点比较：场景、景别、",
    "模特动作、光线、色彩、搭配、服装结构呈现、视觉意图、店铺一致性，并沉淀可复用的",
    "构图-动作-卖点-场景 规则。固定筛选条件：{filters JSON}",
  ], true);
  addCodeBlock(s, { left: 48, top: 518, width: 1160, height: 126 }, "每图追加上下文", [
    "IMAGE {index}; store={store_id}; product={product_id}; title={title}; category={category}; pixels={width}x{height} ＋ input_image(detail=high)",
  ]);
  addFooter(s);
  addNotes(s, [`${sources.repo}/research/2026-08-18/scripts/detailed_visual_analysis.py`]);
}

// Appendix A6: complete Experience 2 per-image Sol prompt.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "附录A6/8：体验2逐图 Sol完整Prompt", "Prompt appendix · experience 2 observations", pageNumber++,
    "该Prompt在每个8图批次重复使用；图片上下文保留角色、品牌和竞品证据入选原因。");
  addCodeBlock(s, { left: 48, top: 164, width: 1160, height: 318 }, "_image_prompt() 完整文本", [
    "你是女装品牌视觉诊断分析师。逐张分析高清商品图，先记录肉眼可见事实，再写优缺点。",
    "不得使用销量、曝光、点击、转化或ROI，不得推断敏感属性。旧分类标签仅是上下文，",
    "不能替代本次观察。证据线索必须能在图片中复核。竞品图只用于对照，不代表目标店铺。",
    "竞品图由全量视觉维度分布分层选出；selection_reasons说明其典型或边界证据角色。",
  ], true);
  addCodeBlock(s, { left: 48, top: 506, width: 1160, height: 138 }, "每图追加上下文", [
    "{image_id, store_id, product_id, category, role, selection_reasons}",
    "＋ input_image(detail=high)",
    "严格Schema要求每张图返回10项observable、visual_role、strengths、weaknesses、evidence_cues、confidence。",
  ]);
  addFooter(s);
  addNotes(s, [`${sources.repo}/research/2026-08-18/scripts/report_analysis_model.py`]);
}

// Appendix A7: complete Experience 2 synthesis prompt.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "附录A7/8：体验2五章汇总 Sol完整Prompt", "Prompt appendix · experience 2 synthesis", pageNumber++,
    "该Prompt只调用一次；末尾拼接scope JSON与完整EVIDENCE JSON，五章在同一响应中返回。");
  addCodeBlock(s, { left: 48, top: 164, width: 1160, height: 482 }, "_synthesis_prompt(scope) 完整文本", [
    "基于逐图观察与批次模式，生成模仿品牌视觉诊断成品PDF结构的专项分析草稿。每条结论必须说明推导方法，",
    "列支持图、反例图、代表图、样本数和观察字段；不得引用未提供的图片ID。目标店铺全量图片用于结论，",
    "竞品高清分层证据集只用于视觉差距。竞品模式判断必须以competitor_evidence中的全量维度分布为分母，",
    "高清代表图只用于复核典型模式与边界反例，不得把代表图数量冒充全量占比。competitive_gap必须分别包含",
    "Princess Polly、Motel Rocks、PrettyLittleThing三家品牌，每家至少一条独立结论；结论或推导必须写出品牌名，",
    "支持图或代表图必须来自该品牌。不得写销售、流量、点击、转化或ROI结论。五个章节必须各出现一次：",
    "brand_positioning=品牌视觉定位校准；product_display=商品展示分析；store_visual_audit=店铺视觉审计；",
    "competitive_gap=竞品视觉差距；visual_upgrade=视觉升级方向。范围：{scope JSON}",
    "EVIDENCE:{complete evidence JSON}",
  ], true);
  addFooter(s);
  addNotes(s, [`${sources.repo}/research/2026-08-18/scripts/report_analysis_model.py`]);
}

// Appendix A8: complete section revision prompt.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "附录A8/8：单章修订 Sol完整Prompt", "Prompt appendix · section revision", pageNumber++,
    "用户判定某章不满意时，只重跑该section；其他四章不重新分析，已完成逐图观察也不重做。");
  addCodeBlock(s, { left: 48, top: 164, width: 1160, height: 376 }, "revise(section, suggestion, evidence, scope) 完整文本", [
    "根据审核意见重新分析一个视觉诊断章节。只能使用给定证据，不得编造图片ID。",
    "保留可支持的结论，修改证据不足或表达不清的部分。输出中文。",
    "",
    "SECTION={current section JSON}",
    "REVIEW={user suggestion}",
    "SCOPE={scope JSON}",
    "EVIDENCE={complete evidence JSON}",
  ], true);
  addBox(s, { left: 48, top: 566, width: 1160, height: 78 }, BLACK, "none", 8);
  addText(s, "修订仍使用单章严格Schema，并再次检查图片ID；若修订competitive_gap，还会再次执行三品牌点名与品牌证据归属校验。",
    { left: 72, top: 588, width: 1112, height: 34 }, { fontSize: 17, bold: true, color: WHITE, alignment: "center" });
  addFooter(s);
  addNotes(s, [
    `${sources.repo}/research/2026-08-18/scripts/report_analysis_model.py`,
    `${sources.repo}/research/2026-08-18/scripts/report_analysis_runner.py`,
  ]);
}

// Discussion.
{
  const s = p.slides.add();
  s.background.fill = BLACK;
  const discussionPage = pageNumber++;
  addText(s, "DISCUSSION", { left: 56, top: 44, width: 280, height: 22 },
    { fontSize: 13, typeface: FONT_LATIN, bold: true, color: "#8FD4F2" });
  addText(s, "下一步，应该把它变成什么？", { left: 56, top: 92, width: 820, height: 72 },
    { fontSize: 42, bold: true, color: WHITE });
  const qs = [
    ["01", "采集边界", "哪些站点继续自动化，哪些登录与验证码环节必须保留人工确认？"],
    ["02", "维度体系", "现有15维是否足够支持视觉决策，还是需要新增品牌专属维度？"],
    ["03", "使用分工", "探索型组合分析与报告型整体分析，分别应该由谁、在何时使用？"],
    ["04", "交付闭环", "PDF止于结论，还是继续连接拍摄brief、图序规范与效果KPI？"],
  ];
  qs.forEach((q, i) => {
    const y = 204 + i * 106;
    addText(s, q[0], { left: 58, top: y, width: 56, height: 34 },
      { fontSize: 18, typeface: FONT_LATIN, bold: true, color: "#8FD4F2" });
    addText(s, q[1], { left: 140, top: y - 2, width: 180, height: 40 },
      { fontSize: 24, bold: true, color: WHITE });
    addText(s, q[2], { left: 360, top: y - 4, width: 790, height: 56 },
      { fontSize: 20, color: "#D0D0D0" });
    if (i < 3) addRule(s, 140, y + 70, 1010, "#343434");
  });
  addText(s, "Fashion Scope", { left: 56, top: 662, width: 200, height: 20 },
    { fontSize: 12, typeface: FONT_LATIN, color: "#767A82" });
  addText(s, String(discussionPage).padStart(2, "0"), { left: 1185, top: 662, width: 46, height: 20 },
    { fontSize: 12, typeface: FONT_LATIN, color: "#767A82", alignment: "right" });
  addNotes(s, ["Internal synthesis based on the verified Fashion Scope product and report workflow."]);
}

await fs.mkdir(RENDERS, { recursive: true });
for (const [index, slide] of p.slides.items.entries()) {
  const stem = `slide-${String(index + 1).padStart(2, "0")}`;
  await writeBlob(path.join(RENDERS, `${stem}.png`), await p.export({ slide, format: "png", scale: 1 }));
  const layout = await slide.export({ format: "layout" });
  await fs.writeFile(path.join(RENDERS, `${stem}.layout.json`), await layout.text());
}
await writeBlob(path.join(RENDERS, "montage.webp"), await p.export({ format: "webp", montage: true, scale: 1 }));
const snapshot = await p.inspect({ kind: "slide,textbox,shape,image,notes", maxChars: 100000 });
await fs.writeFile(path.join(TMP, "deck-inspect.ndjson"), snapshot.ndjson, "utf8");
const pptx = await PresentationFile.exportPptx(p);
await pptx.save(FINAL);
console.log(JSON.stringify({ final: FINAL, slides: p.slides.items.length, renders: RENDERS }));
