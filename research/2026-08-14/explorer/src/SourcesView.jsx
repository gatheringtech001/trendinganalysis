import React from "react";
import { formatNumber, stores } from "./api";

const coverage = [
  { store: "Princess Polly", adapter: "Shopify 官方目录 API", products: 17008, images: 119205, reviews: "500（商品级）", ugc: "100 / 9" },
  { store: "Motel Rocks", adapter: "Shopify 官方目录 API", products: 4422, images: 26676, reviews: "28（品牌级）", ugc: "100 / 3" },
  { store: "PrettyLittleThing", adapter: "官方搜索索引", products: 25495, images: 128152, reviews: "36（品牌级）", ugc: "100 / 7" },
  { store: "Aloruh(shein)", adapter: "SHEIN SG 官方目录 + 商品页", products: 2606, images: 1425, reviews: "0（证据缺失）", ugc: "0 / 0" },
  { store: "Aloruh(local)", adapter: "自有站快照 + 客户本地上传", products: 10487, images: 10782, reviews: "0（证据缺失）", ugc: "0 / 0" },
];
const coverageTotals = coverage.reduce((totals, row) => ({
  products: totals.products + row.products,
  images: totals.images + row.images,
}), { products: 0, images: 0 });

const steps = [
  ["01", "目录采集", "Princess Polly、Motel 读取 Shopify；PLT 遍历美国站官方搜索索引；Aloruh(shein) 单独读取 SHEIN SG，Aloruh(local) 只合并自有站快照与客户本地上传。SHEIN SG 通过可见内置浏览器读取 26 页：3,006 张原始卡片，默认排序去重后 2,560 款。"],
  ["02", "字段标准化", "按店铺 + 商品 ID 去重，统一市场、渠道、目录、详情与图片字段；SHEIN 数字类目映射为可读类目，商品页详情覆盖颜色、尺码、库存、变体与高清图片。"],
  ["03", "分层抽样", "Aloruh SHEIN SG 选择 Most Popular 50、New Arrivals 50、长尾 50；三层严格去重。长尾按折扣/原价各 25 款，并在品类 × 价格带之间轮转抽样。"],
  ["04", "外部证据", "前三店沿用已留存 WebIQ 来源；Aloruh 本轮 WebIQ 鉴权不可用，只保留官网事实，并把评论、UGC、受众证据明确记为缺失。"],
  ["05", "只读分析", "标准化数据写入本地 SQLite；分类、价格、热度、评论、视觉特征和候选竞品 SKU 都读取同一快照，不写回外部站点。"],
];

const backlog = [
  { phase: "P0 · 证据补采", cadence: "一次性", work: "原生 Instagram、TikTok、YouTube 帖子日期与公开互动；创作者、标签、评论主题及关联商品。", done: "帖子原始链接、平台发布日期、互动字段可追溯；失败项明确记录原因。" },
  { phase: "P0 · 评论补采", cadence: "一次性", work: "继续查找 Motel、PLT 与 Aloruh 的商品评论组件；如需登录，由用户本人完成登录，仅做只读采集。", done: "能关联 SKU 的评论单独入库；不可访问时保留证据缺口，不以品牌评论替代。" },
  { phase: "P1 · 投放信号", cadence: "每周", work: "Meta Ad Library、TikTok Creative Center、Google Ads Transparency 的在投素材、落地页、首次/末次观察时间。", done: "同一素材去重，保留平台广告 ID、观察日期、素材哈希和关联商品。" },
  { phase: "P1 · 视觉标签", cadence: "月度增量", work: "Aloruh 客户数据集 10,468 张图片已完成商品类别、廓形版型、设计元素、穿着场景、构图、动作、卖点、场景、材质、色彩图案、视觉语言和搭配方式 12 维分析。", done: "新增图片沿用固定标签字典增量分析；其他店铺尚未补齐同口径标签，不做跨店覆盖率比较。" },
  { phase: "P1 · 趋势信号", cadence: "每月", work: "Google、Pinterest、TikTok 搜索趋势，以及第三方流量与聚合受众估算。", done: "第三方数值标记为估算，记录地区、统计窗口、供应商和抓取日期。" },
  { phase: "P2 · 时间序列", cadence: "持续 8–12 周", work: "每周全量目录；每日或每 2–3 日采集 Top 商品价格、排名、库存、Top Seller 和公开浏览量。", done: "形成至少 8 个周快照后，再判断趋势速度、持续性和跨源共振。" },
];

function SectionTitle({ eyebrow, title, note }) {
  return (
    <div className="sources-heading">
      <div><span>{eyebrow}</span><h2>{title}</h2></div>
      {note && <p>{note}</p>}
    </div>
  );
}

export default function SourcesView({ summary, store }) {
  const selectedLabel = stores[store] || "五个数据源合计";
  return (
    <div className="sources-view">
      <section className="sources-hero">
        <div>
          <span className="sources-kicker">RESEARCH PROTOCOL · V1</span>
          <h2>一份可复核、但有明确边界的外部研究快照</h2>
          <p>研究对象为四个品牌、五个独立数据源：三个美国市场公开目录，以及拆开的 Aloruh(shein) 与 Aloruh(local)。目录快照合并至 {summary.snapshot}，外部近期窗口仍为 2026-05-16 至 2026-08-14。SG 价格、Estimated sold 与榜单不作为美国市场成交数据；两个 Aloruh 数据源均缺评论与 UGC，不据此补写受众结论。</p>
        </div>
        <dl className="sources-snapshot">
          <div><dt>当前筛选</dt><dd>{selectedLabel}</dd></div>
          <div><dt>商品记录</dt><dd>{formatNumber(summary.metrics.products)}</dd></div>
          <div><dt>图片索引</dt><dd>{formatNumber(summary.metrics.images)}</dd></div>
          <div><dt>市场 / 模式</dt><dd>US主样本 + SG补充 / 只读</dd></div>
        </dl>
      </section>

      <section className="sources-section">
        <SectionTitle eyebrow="01 · COVERAGE" title="当前数据覆盖" note="UGC 显示“候选数 / 落入近期窗口数”" />
        <div className="sources-table-wrap">
          <table className="sources-table">
            <thead><tr><th>店铺</th><th>目录适配器</th><th>商品记录</th><th>图片索引</th><th>评论</th><th>UGC</th></tr></thead>
            <tbody>{coverage.map((row) => <tr key={row.store}><td><strong>{row.store}</strong></td><td>{row.adapter}</td><td>{formatNumber(row.products)}</td><td>{formatNumber(row.images)}</td><td>{row.reviews}</td><td>{row.ugc}</td></tr>)}</tbody>
            <tfoot><tr><td>合计</td><td>官网 + 客户数据 + 已留存 WebIQ</td><td>{formatNumber(coverageTotals.products)}</td><td>{formatNumber(coverageTotals.images)}</td><td>564</td><td>300 / 19</td></tr></tfoot>
          </table>
        </div>
        <p className="sources-footnote">三家美国大目录各有 150 款深度样本；Aloruh(shein) 含 2,606 款唯一 SKU（默认目录 2,560 + 排序页新增 46）和 1,425 张图片索引，其中 150 款取得完整商品页详情、1,105 张多角度高清图。Aloruh(local) 含自有站 19 款与客户本地上传 10,468 款，共 10,487 款 / 10,782 张图；客户包中的 354 张唯一 JPG 只标记为本地副本，不重复写入索引。图片索引保存 URL SHA-256，持久化文件才保存文件字节 SHA-256。</p>
      </section>

      <section className="sources-section">
        <SectionTitle eyebrow="02 · PIPELINE" title="从公开页面到分析结果" note="当前实现的实际数据链路" />
        <div className="sources-steps">
          {steps.map(([number, title, body]) => <article key={number}><span>{number}</span><h3>{title}</h3><p>{body}</p></article>)}
        </div>
      </section>

      <section className="sources-section sources-two-column">
        <div>
          <SectionTitle eyebrow="03 · ADAPTERS" title="店铺采集方法" />
          <div className="sources-stack">
            <article><h3>Princess Polly</h3><p>读取美国站 Shopify 全量商品目录和 New、Best Selling、Sale 集合。商品级官方评论最多保留 500 条，可关联商品 ID、评分、日期、验证购买、场景和主题。</p></article>
            <article><h3>Motel Rocks</h3><p>读取美国站 Shopify 全量目录和 New In、Sale 集合；Best/Trending 由官方商品标签中的 best、most wanted、trending、viral 等信号识别。当前评论仅为第三方品牌级片段。</p></article>
            <article><h3>PrettyLittleThing</h3><p>遍历美国站官方搜索索引，并读取 New In、Best Sellers、Sale 排名。索引提供浏览量、Top Seller 与可售数量字段；同款多颜色会重复，分析时按商品 handle 组成的商品族去重。</p></article>
            <article><h3>Aloruh(shein)</h3><p>只保留 SHEIN SG 官方渠道 2,606 款 / 1,425 张图。默认目录读取 26 页，排序页补充 46 个唯一 SKU；150 款商品页通过 ProductGroup JSON-LD 提取颜色、尺码、变体、库存、价格区间和 1,105 张高清图。</p></article>
            <article><h3>Aloruh(local)</h3><p>只保留自有站快照 19 款 / 314 张图与客户本地上传 10,468 条 SKC 图片记录，共 10,487 款 / 10,782 张图；不混入 SHEIN 商品。客户图片已用 Azure OpenAI gpt-5.6-terra 完成固定 12 维视觉分析。</p></article>
          </div>
        </div>
        <div>
          <SectionTitle eyebrow="04 · FIELDS" title="标准化与去重" />
          <div className="field-groups">
            <article><h3>来源</h3><p>store_id、market、channel、source_type、source_url、retrieved_at、content_hash。</p></article>
            <article><h3>商品</h3><p>商品 ID、handle、分类、分类方法/置信度、价格/原价、折扣、颜色、尺码、可售状态、目录顺序、图片链接、Top Seller、公开浏览量。</p></article>
            <article><h3>评论与 UGC</h3><p>日期、评分、主题、情绪、使用场景、平台、来源链接和近期窗口标记；仅做匿名聚合，不建立个人档案。</p></article>
            <article><h3>唯一性规则</h3><p>商品以“店铺 + 商品 ID”唯一；图片以“店铺 + 商品 ID + 位置”唯一；评论以“店铺 + 评论 ID”唯一；内容与图片 URL 使用 SHA-256 追踪。</p></article>
          </div>
        </div>
      </section>

      <section className="sources-section">
        <SectionTitle eyebrow="05 · ANALYSIS MODELS" title="视觉与候选竞品 SKU 怎么计算" note="可复算特征与人工判断分开保存" />
        <div className="field-groups">
          <article><h3>视觉量化</h3><p>对已下载主图统一计算 HSV 平均亮度/饱和度、RGB 冷暖差、Canny 边缘密度、图片边框明暗/饱和度和中性浅背景比例；每店标注实际有效样本数。</p></article>
          <article><h3>视觉人工复核</h3><p>把每店主图排成接触表，人工复核模特、场景、构图和视觉语言。当前结论只覆盖 90 张有效主图，不把结果外推到 284,815 张图片索引。</p></article>
          <article><h3>客户图片 12 维分析</h3><p>Aloruh 客户数据集的 10,468 张图片逐张保存完整标签和维度置信度；维度页按图片数聚合，多标签图片可同时计入多个标签。该结果不外推至其他店铺未分析图片。</p></article>
          <article><h3>候选 SKU 匹配</h3><p>同品类是硬条件；基础同品类 45 分、价格接近最多 25 分、标题/风格词相似最多 20 分、可用单品热度代理最多加 10 分。每店候选池最多 120 款。</p></article>
          <article><h3>解释边界</h3><p>候选对只用于发现可能的商品替代关系。浏览量周期未知，商品评论仅 Princess Polly 可归因；PLT Top Seller 与 Aloruh SHEIN SG Estimated sold / Bestseller 均是不同口径代理，因此匹配分不是销量、竞争强度或消费者真实比较概率。</p></article>
        </div>
      </section>

      <section className="sources-section">
        <SectionTitle eyebrow="06 · INTERPRETATION" title="销量、浏览量与评论怎么解释" note="代理指标不能升级成真实销量" />
        <div className="evidence-cards">
          <article className="boundary-card"><span>不可公开比较</span><h3>真实销量</h3><strong>五个数据源均无同口径公开商品销量</strong><p>Aloruh(shein) 有 32 款显示 Estimated sold、91 款显示 Bestseller 榜单；页面明确标为公开代理，不把它们改写为真实订单量或跨店销售排名。</p></article>
          <article><span>可见但有限</span><h3>公开浏览量</h3><strong>仅 PLT 25,495 条记录</strong><p>按商品族去重后 19,336 款，Top Seller 3,639 条。统计周期未知，因此只可做同源横截面排序，不能解释为当日或月度销量。</p></article>
          <article><span>覆盖不均</span><h3>评论</h3><strong>500 商品级 + 64 品牌级</strong><p>Princess Polly 的 500 条可关联 SKU；Motel 28 条、PLT 36 条是第三方品牌级片段；两个 Aloruh 数据源均为 0 条。缺失不能解释为没有消费者评价。</p></article>
          <article><span>候选发现</span><h3>UGC</h3><strong>前三店各 100 条；两个 Aloruh 数据源均为 0</strong><p>WebIQ 候选只用于主题发现。Aloruh 本轮没有可靠 UGC 候选，不能据此判断其客群或趋势。</p></article>
        </div>
      </section>

      <section className="sources-section sources-two-column">
        <div>
          <SectionTitle eyebrow="07 · EVIDENCE" title="证据等级与结论规则" />
          <ol className="evidence-rules">
            <li><b>官方事实 · High</b><span>官网目录、商品页、官方搜索索引和品牌自述。可以描述当前页面事实。</span></li>
            <li><b>第三方估算 · Medium</b><span>流量、受众、评论平台或行业报道。必须标出供应商、周期与估算属性。</span></li>
            <li><b>分析推断 · Low–Medium</b><span>由多项代理指标形成的客群、视觉和优化假设；关键结论尽量使用两个独立来源交叉验证。</span></li>
          </ol>
        </div>
        <div>
          <SectionTitle eyebrow="08 · QA & SAFETY" title="质量、隐私与采集边界" />
          <ul className="qa-list">
            <li>全量目录解析后核对商品、图片、样本、评论与 UGC 表数量；Aloruh(shein) 验收 2,606 款 / 1,425 张图 / 150 款详情，Aloruh(local) 验收 10,487 款 / 10,782 张图，合计仍为 13,093 款 / 12,207 张图。</li>
            <li>失败请求最多重试 3 次；未取得的数据明确标为缺失，不重复或合成记录补齐。</li>
            <li>不绕过付费墙、验证码或反爬机制；遇到 SHEIN 909 验证时停止，由用户本人完成，不发布、点赞、关注、留言或提交表单。</li>
            <li>本轮由用户本人在内置浏览器登录并完成验证；采集过程不读取或导出密码、Cookie、Token、请求头或风险参数。</li>
            <li>Aloruh 已归档 robots.txt 与 WordPress Sitemap；前三店尚未补做同类规则快照，列为后续 QA 项。</li>
          </ul>
        </div>
      </section>

      <section className="sources-section">
        <SectionTitle eyebrow="09 · NEXT WORK" title="后续需要完成的工作" note="先补证据，再形成可比较的时间序列" />
        <div className="backlog-list">
          {backlog.map((item) => <article key={item.phase}><div><span>{item.phase}</span><b>{item.cadence}</b></div><p>{item.work}</p><small>验收：{item.done}</small></article>)}
        </div>
      </section>

      <section className="sources-section internal-data">
        <div><span>INTERNAL DATA GATE</span><h2>外部研究无法补齐的经营证据</h2></div>
        <p>真实销量、订单、GMV、转化、加购、复购、LTV、退货率和真实广告 ROI 必须接入品牌内部数据后验证。在此之前，所有优化建议都只能标记为“待内部销售/转化数据验证”的假设。</p>
      </section>

      <footer className="sources-provenance">原始官网快照保留在 2026-08-14 研究数据包，客户导入与分类记录保留在 2026-08-18 数据包；标准化数据继续保存来源链接、采集时间与哈希。WebIQ 的 crawledAt 是抓取元数据，不作为内容发布日期。</footer>
    </div>
  );
}
