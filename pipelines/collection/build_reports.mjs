import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const dataDir = path.join(projectRoot, "data");
const analysisDir = path.join(projectRoot, "output", "analysis");
const stores = ["princess_polly", "motel", "prettylittlething"];

const readJson = async file => JSON.parse(await fs.readFile(file, "utf8"));
const analysis = await readJson(path.join(analysisDir, "analysis_summary.json"));
const visual = await readJson(path.join(analysisDir, "visual_notes.json"));
const content = await readJson(path.join(analysisDir, "report_content.json"));
const sqlData = await readJson(path.join(analysisDir, "report_sql_output.json"));
const samples = Object.fromEntries(await Promise.all(stores.map(async store => [store, await readJson(path.join(dataDir, `sample_${store}.json`))])));

const officialUrls = {
  princess_polly: "https://us.princesspolly.com/pages/about-us",
  motel: "https://us.motelrocks.com/pages/about-us",
  prettylittlething: "https://www.prettylittlething.com/pages/informational/about-us",
};
const recentWindows = {
  princess_polly: "9/100",
  motel: "3/100",
  prettylittlething: "7/100",
};
const reportNames = {
  princess_polly: "Princess Polly美国市场外部自我画像研究",
  motel: "Motel Rocks美国市场外部自我画像研究",
  prettylittlething: "PrettyLittleThing美国市场外部自我画像研究",
};
const reportTitles = {
  princess_polly: "Princess Polly 美国外部画像",
  motel: "Motel Rocks 美国外部画像",
  prettylittlething: "PrettyLittleThing 美国外部画像",
};

function median(values) {
  const sorted = values.filter(Number.isFinite).sort((a, b) => a - b);
  if (!sorted.length) return null;
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}
function pct(count, total) { return total ? count / total : null; }
function list(items) { return items.map(item => `- ${item}`).join("\n"); }
function summaryBullets(items) { return items.map(item => `- **${item.split("。")[0]}。**${item.includes("。") ? item.slice(item.indexOf("。") + 1) : ""}`).join("\n"); }

function source(id, label, file, description, url = null) {
  if (!url) return { id, label, path: file, description };
  return {
    id, label, path: file, description,
    query: { engine: "web", description, executed_at: "2026-08-14T00:00:00+08:00", url },
  };
}

function build(store) {
  const a = analysis[store];
  const c = content[store];
  const sample = samples[store];
  const byBucket = sqlData[store].bucket_price;
  const categories = sqlData[store].categories;
  const themes = sqlData[store].review_themes;
  const hypotheses = sqlData[store].hypotheses;
  const coverage = sqlData[store].coverage;
  const sourceList = [
    source("report_sql", "报告聚合SQL", "queries/report_queries.sql", "实际执行的SQLite查询，生成所有原生卡片、图表和表格数据。"),
    source("catalog_snapshot", "官方商品目录快照", `data/catalog_${store}.jsonl`, "2026-08-14美国站当前目录标准化快照。"),
    source("sample_snapshot", "150款分层样本", `data/sample_${store}.json`, "New、Best/Trending、Sale/长尾各50款去重样本。"),
    source("review_snapshot", "评论标准化数据", `data/reviews_${store}.json`, "匿名商品评论或公开第三方摘要记录。"),
    source("ugc_snapshot", "UGC候选数据", `data/ugc_${store}.json`, "公开图片和视频候选，包含平台、日期和原始链接。"),
    source("visual_analysis", "视觉样本人工标注", "analysis/visual_notes.json", "24张商品主图与公开页面视口人工视觉检查。"),
    source("analysis_synthesis", "分析与优化假设", "analysis/report_content.json", "由目录、样本、评论、UGC、视觉与外部来源形成的可审计综合判断。"),
    source("official_about", "品牌官方About", `web/${store}-official-about`, "品牌官方定位和目标客群表述。", officialUrls[store]),
  ];

  const cards = [
    { id: "catalog_count", dataset: "summary", sourceId: "report_sql", description: "已观察官方当前索引记录数。", metrics: [{ label: "目录商品", field: "catalog_rows", format: "number" }] },
    { id: "sample_price", dataset: "summary", sourceId: "report_sql", description: "150款分层样本的价格中位数。", metrics: [{ label: "样本价格中位数", field: "sample_median_price", format: "currency" }] },
    { id: "sample_availability", dataset: "summary", sourceId: "report_sql", description: "150款样本中至少一个规格可售的占比。", metrics: [{ label: "样本可售率", field: "sample_available_rate", format: "percent" }] },
    { id: "review_count", dataset: "summary", sourceId: "report_sql", description: store === "princess_polly" ? "匿名商品评论记录。" : "公开可得的摘要级评论记录。", metrics: [{ label: "评论记录", field: "review_count", format: "number" }] },
  ];
  const charts = [
    {
      id: "price_by_bucket", title: "150款样本价格层级", subtitle: "每层50款，单位为美元；不表示销量。", type: "bar", dataset: "bucket_price", sourceId: "report_sql",
      encodings: { x: { field: "bucket", type: "ordinal", label: "样本层" }, y: { field: "median_price_usd", type: "quantitative", label: "价格中位数", format: "currency" } },
      yAxisTitle: "价格中位数（USD）", valueFormat: "currency", layout: "full",
    },
    {
      id: "category_structure", title: "目录核心品类", subtitle: "按官方目录标签统计前7类；大小写已合并。", type: "bar", dataset: "categories", sourceId: "report_sql",
      encodings: { x: { field: "category", type: "ordinal", label: "品类" }, y: { field: "products", type: "quantitative", label: "商品数", format: "number" } },
      yAxisTitle: "商品数", valueFormat: "number", layout: "full",
    },
  ];
  const tables = [
    { id: "coverage", title: "数据覆盖与边界", dataset: "coverage", sourceId: "report_sql", defaultSort: { field: "item", direction: "asc" }, columns: [
      { field: "item", label: "数据项", type: "text" }, { field: "actual", label: "实际数量", format: "number" }, { field: "target", label: "目标/口径", type: "text" }, { field: "note", label: "边界", type: "text" },
    ] },
    { id: "review_themes", title: "评论主题", dataset: "review_themes", sourceId: "report_sql", defaultSort: { field: "mentions", direction: "desc" }, columns: [
      { field: "theme", label: "主题", type: "text" }, { field: "mentions", label: "记录数", format: "number" },
    ] },
  ];
  const blocks = [
    { id: "title", type: "markdown", body: `# ${reportTitles[store]}` },
    { id: "executive_summary", type: "markdown", body: `## Executive Summary\n\n${summaryBullets(c.executive_summary)}` },
    { id: "coverage_intro", type: "markdown", body: "## 方法与覆盖率：目录完整，评论深度不均\n\n本报告快照日为2026年8月14日，美国市场；150款样本按New、Best/Trending、Sale/长尾各50款。目录解析覆盖率只表示已观察官方索引记录全部标准化成功，不声称掌握未知真实SKU总量。" },
    { id: "coverage_table", type: "table", tableId: "coverage", layout: "full" },
    { id: "headline_metrics", type: "metric-strip", cardIds: cards.map(card => card.id) },
    { id: "price_intro", type: "markdown", sourceId: "sample_snapshot", body: `## 商品与价格：当前层级样本比全目录更接近消费者所见\n\n150款样本价格中位数为 **$${a.sample.price_median_usd.toFixed(2)}**，可售率为 **${(a.sample.available_rate * 100).toFixed(1)}%**，促销率为 **${(a.sample.on_sale_rate * 100).toFixed(1)}%**。下图分别展示三个店内层级，差异只能解释为当前商品结构，不能解释为销量。` },
    { id: "price_chart", type: "chart", chartId: "price_by_bucket", layout: "full" },
    { id: "price_implication", type: "markdown", body: `**如何解读。** ${store === "princess_polly" ? "全目录与当前样本差距大，长尾售罄/促销状态可能放大目录层指标；商品生命周期治理比简单追求SKU数更重要。" : store === "motel" ? "全目录与样本的价格中位数接近，说明当前货盘与总体价格带相对一致；促销和版型信息仍需与退货数据联读。" : "三个层级都保持强折扣，说明价值锚定是结构性特征；‘elevated’叙事需要更清晰的商品分层来避免永久折扣疲劳。"}` },
    { id: "category_intro", type: "markdown", sourceId: "catalog_snapshot", body: `## 品类结构：${categories.slice(0, 3).map(row => row.category).join("、")}构成主要供给\n\n图中为全量目录前7个品类，已合并大小写标签。它反映供给规模而非售出规模；若要判断品类效率，仍需内部销售、转化和毛利。` },
    { id: "category_chart", type: "chart", chartId: "category_structure", layout: "full" },
    { id: "audience", type: "markdown", body: `## 客群画像：官方定位与外部观察${store === "princess_polly" ? "高度一致" : store === "motel" ? "方向一致，但人口统计证据薄弱" : "覆盖广，但美国人口统计仍缺失"}\n\n${c.audience.map(item => `- **${item.confidence}置信度：** ${item.statement}`).join("\n")}` },
    { id: "review_intro", type: "markdown", sourceId: "review_snapshot", body: `## 口碑与UGC：${store === "princess_polly" ? "商品评论可支持场景和尺码判断" : "评论只能支持方向性假设"}\n\n本轮获得 **${a.reviews.count}** 条评论记录和 **${a.ugc.count}** 条公开UGC候选；其中可确认落在近90天窗口的UGC为 **${a.ugc.recent_window_count}** 条。${store === "princess_polly" ? `商品评论平均评分 **${a.reviews.average_rating.toFixed(2)}**，但评分不等于复购或转化。` : "评论为第三方摘要级记录，未保留可验证评分与人口统计，不能外推整体满意度。"}` },
    { id: "review_table", type: "table", tableId: "review_themes", layout: "full" },
    { id: "visual", type: "markdown", sourceId: "visual_analysis", body: `## 视觉系统：${visual[store].style_system}\n\n**模特与场景。** ${visual[store].model_and_scene}\n\n**构图与色彩。** ${visual[store].composition} ${visual[store].colour_and_light}\n\n**一致性。** ${visual[store].consistency}` },
    { id: "consistency", type: "markdown", body: `## 定位一致与偏差：保留优势，明确证据缺口\n\n${list(c.consistency)}` },
    { id: "recommendations", type: "markdown", body: `## 推荐下一步：把假设做成可测实验\n\n以下建议按现有证据强度排序，不是已经验证的方案。\n\n${c.hypotheses.map(item => `${item.priority}. **${item.hypothesis}**\n   - 证据：${item.evidence}\n   - 置信度：${item.confidence}\n   - 预期影响：${item.impact}\n   - ${item.validation}`).join("\n")}` },
    { id: "further_questions", type: "markdown", body: "## Further questions\n\n1. 哪些品类、尺码和价格带真正贡献美国GMV、毛利与新客转化？\n2. 首图、折扣、尺码提示和场景标签对点击、加购、退货的增量分别是多少？\n3. 公开UGC与站内购买者在年龄、场景和审美上是否存在系统偏差？" },
    { id: "caveats", type: "markdown", body: `## Caveats and assumptions\n\n- 不推算销量；Bestseller层、评论量、售罄率、折扣、互动和浏览字段均为代理。\n- 客群仅保留匿名聚合，不建立个人档案。\n- ${store === "prettylittlething" ? "PLT首页与New In页面在采集环境返回CloudFront 403，视觉分析仅使用24张商品主图。" : "页面截图为单一桌面视口，不代表全部设备或全部活动周期。"}\n- 评论和UGC受公开可得性、搜索索引日期与平台访问限制影响。\n- 所有优化假设仍需内部销售、转化和利润数据验证。` },
  ];

  return {
    surface: "report",
    manifest: { version: 1, surface: "report", title: reportTitles[store], description: `${c.name}美国市场第一闭环外部自我画像。`, generatedAt: "2026-08-14T00:00:00+08:00", cards, charts, tables, sources: sourceList, blocks },
    snapshot: { version: 1, generatedAt: "2026-08-14T00:00:00+08:00", status: "ready", datasets: {
      summary: sqlData[store].summary,
      bucket_price: byBucket, categories, review_themes: themes, hypotheses, coverage,
    } },
    sources: sourceList,
    package_info: { root: store, manifestPath: "artifact.json", snapshotPath: "artifact.json" },
  };
}

for (const store of stores) {
  const dir = path.join(projectRoot, "output", "reports", store);
  await fs.mkdir(dir, { recursive: true });
  const artifact = build(store);
  await fs.writeFile(path.join(dir, "artifact.json"), JSON.stringify(artifact, null, 2));
  console.log(`${store}: ${artifact.manifest.blocks.length} blocks, ${Object.keys(artifact.snapshot.datasets).length} datasets, output=${reportNames[store]}.html`);
}
