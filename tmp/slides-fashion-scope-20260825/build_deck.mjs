import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const TMP = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(TMP, "..", "..");
const ASSETS = path.join(TMP, "assets");
const RENDERS = path.join(TMP, "renders");
const FINAL = path.join(ROOT, "output", "Fashion-Scope-技术架构与产品体验-20260826-v6.pptx");

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
    ["Aloruh（SHEIN）", "2,848", "4,352", "343", 4352],
    ["Aloruh local", "10,487", "10,771", "10,466", 10771],
    ["Princess Polly", "17,008", "119,205", "5,613", 119205],
    ["Motel Rocks", "4,422", "26,676", "2,141", 26676],
    ["PrettyLittleThing", "25,495", "127,827", "7,353", 127827],
  ];
  const headerTop = 266;
  addBox(s, { left: 48, top: headerTop, width: 1166, height: 42 }, BLACK, "none", 0, "inventory-table-header");
  const headers = [
    ["店铺", 64, 270],
    ["商品记录", 384, 120],
    ["图片URL（条）", 558, 140],
    ["已分析图片", 748, 150],
    ["相对URL数量（最长=PLT）", 950, 240],
  ];
  headers.forEach((header, index) => {
    addText(s, header[0], { left: header[1], top: headerTop + 12, width: header[2], height: 20 },
      { fontSize: 13, bold: true, color: WHITE, alignment: index > 0 && index < 4 ? "right" : "left" }, `inventory-header-${index}`);
  });

  const maxImageIndex = 127827;
  inventory.forEach((row, index) => {
    const top = 308 + index * 52;
    if (index % 2 === 1) addBox(s, { left: 48, top, width: 1166, height: 52 }, "#F7F7F7", "none", 0, `inventory-row-bg-${index}`);
    addText(s, row[0], { left: 64, top: top + 15, width: 270, height: 24 },
      { fontSize: 17, bold: true }, `inventory-store-${index}`);
    addText(s, row[1], { left: 384, top: top + 15, width: 120, height: 24 },
      { fontSize: 17, typeface: FONT_LATIN, alignment: "right" }, `inventory-products-${index}`);
    addText(s, row[2], { left: 548, top: top + 15, width: 150, height: 24 },
      { fontSize: 17, typeface: FONT_LATIN, bold: true, alignment: "right" }, `inventory-images-${index}`);
    addText(s, row[3], { left: 748, top: top + 15, width: 150, height: 24 },
      { fontSize: 17, typeface: FONT_LATIN, alignment: "right", color: MUTED }, `inventory-analyzed-${index}`);
    addBox(s, { left: 950, top: top + 20, width: 240, height: 12 }, "#E1E3E6", "none", 0, `inventory-bar-track-${index}`);
    addBox(s, { left: 950, top: top + 20, width: Math.max(8, 240 * row[4] / maxImageIndex), height: 12 },
      index === 4 ? BLUE : "#8FD4F2", "none", 0, `inventory-bar-${index}`);
    addRule(s, 48, top + 51, 1166, "#E1E3E6");
  });

  addBox(s, { left: 48, top: 582, width: 1166, height: 54 }, BLACK, "none", 0, "inventory-total");
  addText(s, "全站合计", { left: 64, top: 598, width: 250, height: 24 },
    { fontSize: 17, bold: true, color: WHITE }, "inventory-total-label");
  addText(s, "60,260", { left: 384, top: 598, width: 120, height: 24 },
    { fontSize: 17, typeface: FONT_LATIN, bold: true, color: WHITE, alignment: "right" }, "inventory-total-products");
  addText(s, "288,831", { left: 548, top: 598, width: 150, height: 24 },
    { fontSize: 17, typeface: FONT_LATIN, bold: true, color: "#8FD4F2", alignment: "right" }, "inventory-total-images");
  addText(s, "25,916", { left: 748, top: 598, width: 150, height: 24 },
    { fontSize: 17, typeface: FONT_LATIN, bold: true, color: WHITE, alignment: "right" }, "inventory-total-analyzed");
  addText(s, "跨店合并重复URL后：288,513", { left: 950, top: 598, width: 240, height: 24 },
    { fontSize: 14, bold: true, color: "#8FD4F2" }, "inventory-global-dedup");
  addText(s, "读法：1个商品若有5张图，就产生5条图片URL索引；只有用户启动高清分析时，系统才下载并校验图片文件。",
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

// Terra dimension-specific prompt examples.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "不同维度要问不同问题，不能只说“分析图片”", "Layer 2 · Terra prompt examples", pageNumber++,
    "Terra把15维拆成三组可回答的问题；下面是发送给模型的中文化Prompt示例。");
  const promptExamples = [
    ["01", "商品本身", "商品类别 · 廓形版型 · 设计元素 · 材质纹理 · 色彩图案",
      "先找出画面中的主售服装。判断它属于上衣、半身裙、连衣裙或套装中的哪一类；再根据可见轮廓、结构、纹理、颜色和图案选择标签。只标画面或标题能支持的内容，不猜纤维成分。"],
    ["02", "图片怎么拍", "画面构图 · 视角动作 · 卖点部位 · 拍摄场景 · 光线 · 模特状态",
      "判断图片是全身、近景、细节还是纯商品图；记录正面、背面、行走等视角动作；再识别镜头强调的部位、实际场景、光线与模特状态。不要用图片序号推断正背面。"],
    ["03", "语境与表达", "穿着场合 · 视觉语言 · 搭配方式 · 图文叠加",
      "分别判断衣服适合的场合和照片实际拍摄的场景——两者不能混为一谈；再判断视觉风格、搭配方式和是否有文字、拼贴或Logo水印。看不清就返回“无法判断”。"],
  ];
  promptExamples.forEach((example, index) => {
    const top = 164 + index * 146;
    addBox(s, { left: 48, top, width: 1166, height: 132 }, index === 1 ? LIGHT_BLUE : PANEL, "none", 8, `prompt-example-${index}`);
    addText(s, example[0], { left: 70, top: top + 18, width: 44, height: 24 },
      { fontSize: 14, typeface: FONT_LATIN, bold: true, color: index === 1 ? BLUE : MUTED }, `prompt-example-index-${index}`);
    addText(s, example[1], { left: 70, top: top + 50, width: 230, height: 34 },
      { fontSize: 23, bold: true }, `prompt-example-title-${index}`);
    addText(s, example[2], { left: 70, top: top + 88, width: 310, height: 26 },
      { fontSize: 15, bold: true, color: BLUE }, `prompt-example-dimensions-${index}`);
    addText(s, `“${example[3]}”`, { left: 404, top: top + 22, width: 780, height: 92 },
      { fontSize: 17, color: INK }, `prompt-example-body-${index}`);
  });
  addBox(s, { left: 48, top: 620, width: 1152, height: 34 }, BLACK);
  addText(s, "每一维都返回：词典内标签＋0–1置信度；不在词典内的标签、漏维度或重复图片会被程序拒绝。",
    { left: 72, top: 627, width: 1104, height: 20 }, { fontSize: 16, color: WHITE, alignment: "center" });
  addFooter(s);
  addNotes(s, [`${sources.repo}/research/2026-08-18/scripts/azure_openai_fashion_analyzer.py`]);
}

// Sol prompt examples for both user experiences.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "Sol把选中的图片变成可核验结论，不负责重新分类", "Layer 3 · Sol prompt examples", pageNumber++,
    "它只在用户点击分析或启动整体报告时运行；每个判断都必须引用具体图片和肉眼可见的线索。");
  addPromptBlock(s, { left: 48, top: 166, width: 560, height: 396 }, "体验1 / 回答当前筛选问题", [
    "输入：用户选择的维度组合＋手动勾选的高清图片。",
    "",
    "Prompt示例：你正在分析“上衣 × 度假”。对每张图：",
    "1  先写能直接看到的构图、场景、动作、光线与搭配；",
    "2  说明这些线索是否强化“度假”表达；",
    "3  比较不同店铺的做法；",
    "4  每个判断引用图片ID和具体可见线索。",
    "",
    "输出：逐图解释＋店铺差异＋可执行建议。",
  ].join("\n"), true);
  addPromptBlock(s, { left: 640, top: 166, width: 592, height: 396 }, "体验2 / 形成整体报告", [
    "输入：Aloruh目标图片＋竞品全量15维分布＋竞品高清证据图。",
    "",
    "Prompt示例：先分别观察每张图，再按品牌汇总：",
    "1  Princess Polly、Motel Rocks、PrettyLittleThing分别写结论；",
    "2  每条结论说明样本数、推导过程、支持图和反例图；",
    "3  汇总成五个Section，交给用户逐章审核；",
    "4  任何结论都不能脱离输入图片或混用品牌图片。",
    "",
    "输出：五章可审核草稿；通过后再本地排版PDF。",
  ].join("\n"));
  addBox(s, { left: 48, top: 586, width: 1160, height: 70 }, BLACK, "none", 8);
  addText(s, "一句话：Terra回答“这张图是什么标签”；Sol回答“这些图片说明了什么，为什么”。",
    { left: 72, top: 606, width: 1112, height: 30 }, { fontSize: 19, bold: true, color: WHITE, alignment: "center" });
  addFooter(s);
  addNotes(s, [
    `${sources.repo}/research/2026-08-18/scripts/detailed_visual_analysis.py`,
    `${sources.repo}/research/2026-08-18/scripts/report_analysis_model.py`,
    `${sources.repo}/research/2026-08-18/scripts/report_analysis_runner.py`,
  ]);
}

// Experience 1 workflow.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "体验1工作流：先用15维圈定图片集，再按需做精细分析", "Layer 3A · classify + analyze", pageNumber++,
    "这是探索链路：不预先写结论，而是从维度组合进入店铺、商品与图片证据。");
  const topNodes = [
    ["01", "选择1–N个维度", "从15维中自由勾选"],
    ["02", "每维选择1个标签", "例如：商品类别=上衣"],
    ["03", "组合成AND条件", "例如：上衣 AND 度假"],
    ["04", "按店铺返回命中图", "结果保留商品与图片键"],
  ];
  const bottomNodes = [
    ["05", "抽样或手动勾选", "只选需要解释的图片"],
    ["06", "高清校验＋Sol精读", "分析构图、动作与卖点"],
    ["07", "形成可回查结论", "店铺差异、支持图与建议"],
  ];
  for (let i = 0; i < 3; i += 1) {
    flowArrow(s, { position: { left: 298 + i * 294, top: 224, width: 44, height: 48 } });
  }
  flowArrow(s, { text: "↓", position: { left: 1024, top: 336, width: 48, height: 48 } });
  flowArrow(s, { text: "←", position: { left: 884, top: 454, width: 44, height: 48 } });
  flowArrow(s, { text: "←", position: { left: 590, top: 454, width: 44, height: 48 } });
  topNodes.forEach((node, i) => {
    flowNode(s, {
      position: { left: 48 + i * 294, top: 176, width: 250, height: 150 },
      step: node[0], title: node[1], detail: node[2], accent: i === 0,
    });
  });
  bottomNodes.forEach((node, i) => {
    flowNode(s, {
      position: { left: 930 - i * 294, top: 398, width: 250, height: 150 },
      step: node[0], title: node[1], detail: node[2], accent: i === 1,
    });
  });
  addBox(s, { left: 48, top: 586, width: 1132, height: 58 }, BLACK);
  addText(s, "真实示例：商品类别=上衣 AND 穿着场景=度假 → 生产环境命中 3,179 张图片",
    { left: 72, top: 602, width: 1084, height: 30 },
    { fontSize: 18, bold: true, color: WHITE, alignment: "center" });
  addFooter(s);
  addNotes(s, [
    sources.production,
    `${sources.repo}/research/2026-08-14/explorer/src/ImageDimensions.jsx`,
    `${sources.repo}/research/2026-08-18/scripts/analyze_dimension_selection.py`,
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

// Experience 2 workflow.
{
  const s = p.slides.add();
  s.background.fill = WHITE;
  addHeader(s, "体验2工作流：目标店铺全量分析，竞品按全量分布挑选证据", "Layer 3B · full analysis", pageNumber++,
    "先固定范围和证据契约；目标店铺与竞品采用不同取图规则，最终合并成同一报告底座。");
  flowArrow(s, { text: "↗", position: { left: 200, top: 244, width: 64, height: 64 } });
  flowArrow(s, { text: "↘", position: { left: 200, top: 404, width: 64, height: 64 } });
  flowArrow(s, { position: { left: 454, top: 456, width: 46, height: 48 } });
  flowArrow(s, { text: "↘", position: { left: 450, top: 260, width: 64, height: 64 } });
  flowArrow(s, { text: "↗", position: { left: 694, top: 382, width: 64, height: 64 } });
  flowArrow(s, { text: "↗", position: { left: 942, top: 246, width: 64, height: 64 } });
  flowArrow(s, { text: "↓", position: { left: 1078, top: 316, width: 44, height: 48 } });
  flowArrow(s, { text: "↓", position: { left: 1078, top: 492, width: 44, height: 48 } });
  flowNode(s, { position: { left: 48, top: 300, width: 160, height: 142 }, step: "01", title: "固定范围", detail: "TOPS＋SKIRTS\n目标＋竞品", accent: true });
  flowNode(s, { position: { left: 258, top: 184, width: 198, height: 142 }, step: "02A", title: "目标店铺", detail: "386张目标图\n全量高清" });
  flowNode(s, { position: { left: 258, top: 416, width: 198, height: 142 }, step: "02B", title: "竞品分母", detail: "15,107张\n全量维度分布" });
  flowNode(s, { position: { left: 500, top: 416, width: 198, height: 142 }, step: "03", title: "六维分层选证据", detail: "106张高频典型\n＋低频边界" });
  flowNode(s, { position: { left: 744, top: 286, width: 202, height: 166 }, step: "04", title: "共享分析底座", detail: "高清缓存\n492张逐图观察\nGPT-5.6 Sol", accent: true });
  flowNode(s, { position: { left: 994, top: 180, width: 214, height: 134 }, step: "05", title: "五个Section草稿", detail: "结论＋图片角色＋image_id" });
  flowNode(s, { position: { left: 994, top: 360, width: 214, height: 134 }, step: "06", title: "逐章人工审核", detail: "通过 / 修改 / 补图 / 重跑" });
  flowNode(s, { position: { left: 994, top: 542, width: 214, height: 100 }, step: "07", title: "53页PDF\nReportLab / Pillow", detail: "", dark: true });
  addFooter(s);
  addNotes(s, [
    `${sources.repo}/research/2026-08-18/scripts/report_analysis_runner.py`,
    `${sources.repo}/research/2026-08-18/scripts/report_analysis_model.py`,
    `${sources.repo}/research/2026-08-14/explorer/report_pdf.py`,
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
const snapshot = await p.inspect({ kind: "slide,textbox,shape,image,notes", maxChars: 20000 });
await fs.writeFile(path.join(TMP, "deck-inspect.ndjson"), snapshot.ndjson, "utf8");
const pptx = await PresentationFile.exportPptx(p);
await pptx.save(FINAL);
console.log(JSON.stringify({ final: FINAL, slides: p.slides.items.length, renders: RENDERS }));
